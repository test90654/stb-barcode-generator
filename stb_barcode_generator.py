import io
import barcode
from barcode.writer import ImageWriter
from PIL import Image
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成テスト', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード生成・プレビューテスト')
st.write(
    'ご提示いただいた画像（両端に*があり、バーコード幅に文字が揃う形式）に完全に一致させるプレビューページです。'
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

# 2. バーコード設定（ご指定のバランスを反映）
st.subheader('⚙️ バーコードの見た目調整')
col1, col2 = st.columns(2)

with col1:
  # ご指定のバランス
  module_height = st.slider(
      'バーの高さ (module_height)', min_value=5.0, max_value=30.0, value=12.0, step=1.0
  )
  font_size = st.slider(
      '文字の大きさ (font_size)', min_value=6, max_value=24, value=10, step=1
  )

with col2:
  text_distance = st.slider(
      '文字とバーの距離 (text_distance)',
      min_value=1.0,
      max_value=20.0,
      value=6.0,
      step=1.0,
  )
  module_width = st.slider(
      'バーの太さ (module_width)', min_value=0.1, max_value=1.0, value=0.45, step=0.05
  )

# 3. バーコードの生成（ライブラリの標準機能でアスタリスク付き＆幅揃えを実現）
if target_data:
  try:
    code39 = barcode.get_barcode_class('code39')
    
    rv = io.BytesIO()
    # Code39の仕様通り、自動で両端に '*' が付いてバーコード幅に文字が揃う形にします
    barcode_instance = code39(target_data, writer=ImageWriter())

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'font_size': font_size,
        'text_distance': text_distance,
        'quiet_zone': 6.5,
        'write_text': True,  # ライブラリに文字（*付き＆幅揃え）を描画させる
    }

    barcode_instance.write(rv, options=options)
    rv.seek(0)

    # 【重要】文字がバーコードの裏や下に隠れたり切れたりしないよう、Pillowで下部に余白を拡張する
    img = Image.open(rv)
    width, height = img.size
    
    # 追加で下部に持たせる余白の高さ（ピクセル）
    padding_bottom = 25 
    
    # 白背景の新しいキャンバスを作成し、生成したバーコードを上部に貼り付ける
    new_img = Image.new("RGB", (width, height + padding_bottom), "white")
    new_img.paste(img, (0, 0))

    final_rv = io.BytesIO()
    new_img.save(final_rv, format='PNG')
    final_rv.seek(0)

    st.success('理想の形に合わせたバーコードが生成されました！')

    # 画面にプレビュー表示
    st.image(final_rv, caption=f'Code: {target_data}', use_container_width=True)

    # ダウンロードボタン
    st.download_button(
        label='📥 この画像をダウンロードする',
        data=final_rv,
        file_name=f'stb_barcode_{target_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(f'バーコード生成エラー: {e}')
