import io
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成テスト', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード生成・プレビューテスト')
st.write(
    '1つのコードをテスト生成して、ブラウザ上で見た目（高さや文字の重なり）を確認できるページです。'
)

# 1. 入力方法の選択（直接入力か、CSVから読み込むか）
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

    # リストから行番号（インデックス）を選ぶ
    row_index = st.slider(
        '何行目のデータを確認しますか？',
        0,
        len(df) - 1,
        0,
    )
    raw_data = df.iloc[row_index][target_column]

    # 指数表記（例: 1.96222E+11）の自動修復
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

# 2. バーコード設定（ここで見た目を微調整できます）
st.subheader('⚙️ バーコードの見た目調整（プレビューに即時反映）')
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
      max_value=15.0,
      value=7.0,
      step=1.0,
  )
  module_width = st.slider(
      'バーの太さ (module_width)', min_value=0.1, max_value=0.5, value=0.2, step=0.05
  )

# 3. バーコードの生成と画面表示
if target_data:
  try:
    code39 = barcode.get_barcode_class('code39')
    rv = io.BytesIO()
    barcode_instance = code39(target_data, writer=ImageWriter())

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'font_size': font_size,
        'text_distance': text_distance,
        'write_text': True,
    }

    barcode_instance.write(rv, options=options)
    rv.seek(0)

    st.success('バーコードが生成されました！下のプレビューで確認してください。')

    # 画面上に画像を直接表示
    st.image(rv, caption=f'Code: {target_data}', use_container_width=True)

    # 個別ダウンロードボタン
    rv.seek(0)
    st.download_button(
        label='📥 この画像をダウンロードする',
        data=rv,
        file_name=f'stb_barcode_{target_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(
        f'バーコード生成エラー: {e} （※Code 39で使用できない文字が含まれている可能性があります）'
    )
