import io
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコードプレビューツール', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード・画面プレビューツール')
st.write(
    'CSVファイル（A列に管理番号等が入ったファイル）をアップロードすると、画面上で直接すべてのバーコードの見た目を確認できます。'
)

# 1. CSVファイルのアップロード（自動的に先頭列をターゲットにします）
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  df = pd.read_csv(uploaded_file)
  target_column = df.columns[0]

  # データの抽出と指数表記（1.96222E+11など）の自動修復
  cleaned_data_list = []
  for raw_data in df[target_column]:
    try:
      if isinstance(raw_data, float) or (
          isinstance(raw_data, str) and 'e' in raw_data.lower()
      ):
        val = str(int(float(raw_data)))
      else:
        val = str(raw_data).strip()
    except Exception:
      val = str(raw_data).strip()

    if val and val.lower() != 'nan':
      cleaned_data_list.append(val)

  st.success(
      f'✨ CSVから **{len(cleaned_data_list)}件** のデータを正常に読み込みました！'
  )

  # 2. バーコードの設定項目（見た目の微調整）
  st.subheader('⚙️ バーコードの見た目調整')
  col1, col2 = st.columns(2)

  with col1:
    module_height = st.slider(
        'バーの高さ (module_height)',
        min_value=5.0,
        max_value=30.0,
        value=15.0,
        step=1.0,
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

  # 3. 画面上のプレビュー一覧表示（CSVの順番通りにすべて描画）
  st.markdown('---')
  st.subheader('👀 バーコード一覧プレビュー')

  if cleaned_data_list:
    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        code39 = barcode.get_barcode_class('code39')
        barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

        # 【重要】font_path に 'arial.ttf' を指定して、0のドット（点）を解消する
        options = {
            'module_width': module_width,
            'module_height': module_height,
            'font_size': font_size,
            'text_distance': text_distance,
            'quiet_zone': 6.5,
            'write_text': True,
            'font_path': 'arial.ttf',
        }

        # 両端に * と、文字間にスペースを入れたフォーマット
        spaced_text = ' '.join(list(clean_data))
        barcode_instance.default_text = f'* {spaced_text} *'

        rv = io.BytesIO()
        barcode_instance.write(rv, options=options)
        rv.seek(0)

        # 画面に順番通りに画像を表示
        st.image(
            rv,
            caption=f'[{i:03d}] Code: *{spaced_text}*',
            use_container_width=True,
        )
      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
