import io
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成ツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・テスト')
st.write(
    '入力欄にはそのまま文字列を入れ、自動で両端に*と文字間にスペースが入るプレビューページです。'
)

# 1. 入力方法の選択
input_method = st.radio(
    'データの入力方法を選んでください', ('直接入力する', 'CSVファイルから1つ選ぶ')
)

target_data = ''

if input_method == '直接入力する':
  target_data = st.text_input(
      'バーコードにする文字列（例: 19A7B8D90016W）', value='19DDA52A000E'
  )
else:
  uploaded_file = st.file_uploader(
      'テスト用のCSVファイルを選択してください', type=['csv']
  )
  if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    columns = df.columns.tolist()
    target_column = st.selectbox('バーコード化する列を選択:', columns)
    row_index = st.slider('何行目のデータを確認しますか？', 0, len(df) - 1, 0)
    raw_data = df.iloc[row_index][target_column]

    try:
      if isinstance(raw_data, float) or (
          isinstance(raw_data, str) and 'e' in raw_data.lower()
      ):
        target_data = str(int(float(raw_data)))
      else:
        target_data = str(raw_data).strip()
    except Exception:
      target_data = str(raw_data).strip()

    st.write(f'選択されたデータ: **{target_data}**')

# 2. バーコード設定
st.subheader('⚙️ バーコードの設定')
col1, col2 = st.columns(2)

with col1:
  module_height = st.slider(
      'バーの高さ (module_height)', min_value=5.0, max_value=30.0, value=15.0, step=1.0
  )
  font_size = st.slider(
      '文字の大きさ (font_size)', min_value=6, max_value=20, value=10, step=1
  )

with col2:
  text_distance = st.slider(
      '文字とバーの距離 (text_distance)',
      min_value=1.0,
      max_value=20.0,
      value=5.0,
      step=1.0,
  )
  module_width = st.slider(
      'バーの太さ (module_width)', min_value=0.1, max_value=1.0, value=0.3, step=0.05
  )

# 3. バーコード生成
if target_data:
  try:
    # スペースや前後の空白を取り除いたクリーンなデータでバーコードを作成する
    clean_data = target_data.replace(' ', '').strip()
    
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=ImageWriter())

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'font_size': font_size,
        'text_distance': text_distance,
        'quiet_zone': 6.5,
        'write_text': True,
    }

    # バーの生成には正しい clean_data を使いつつ、
    # 描画されるテキスト部分だけを「1文字ずつスペースを入れて両端に*を挟んだ形」に上書きする安全な処理
    spaced_text = ' '.join(list(clean_data))
    barcode_instance.text = f'* {spaced_text} *'

    rv = io.BytesIO()
    # 内部のテキスト書き換えを反映させるため、builderでビルドした後にテキストを強制適用するカスタム処理
    # ImageWriterの描画時に渡されるtextを書き換える
    options_text = f'* {spaced_text} *'
    
    # 確実に文字を置き換えるために writer の text 属性を書き換えて出力
    writer = ImageWriter()
    # python-barcode の描画用テキストをハック
    barcode_instance.default_text = options_text
    
    barcode_instance.write(rv, options=options)
    rv.seek(0)

    st.success('エラーなく生成されました！理想の見た目をご確認ください。')
    st.image(rv, caption=f'Code: *{spaced_text}*', use_container_width=True)

    st.download_button(
        label='📥 この画像をダウンロードする',
        data=rv,
        file_name=f'stb_barcode_{clean_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(f'バーコード生成エラー: {e}')
