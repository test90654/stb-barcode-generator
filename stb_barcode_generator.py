import barcode
from barcode.writer import SVGWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコードプレビューツール', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード・画面プレビューツール（SVG高精度表示）')
st.write(
    'CSVファイル（A列）をアップロードすると、文字崩れのない綺麗なSVGバーコードを画面上で確認できます。'
)

# 1. CSVファイルのアップロード
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  df = pd.read_csv(uploaded_file, header=None)
  target_column = df.columns[0]

  # データの抽出と指数表記の自動修復
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

  # 2. バーコードの設定項目
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
        '文字の大きさ (font_size)', min_value=6, max_value=24, value=12, step=1
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
        'バーの太さ (module_width)', min_value=0.2, max_value=1.0, value=0.4, step=0.05
    )

  # 3. 画面上のプレビュー一覧表示（SVG形式で高精度に描画）
  st.markdown('---')
  st.subheader('👀 バーコード一覧プレビュー')

  if cleaned_data_list:
    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        code39 = barcode.get_barcode_class('code39')
        
        # SVGWriter を使用することで、ブラウザの標準フォント（点のない綺麗な0）で描画させる
        barcode_instance = code39(clean_data, writer=SVGWriter(), add_checksum=False)

        options = {
            'module_width': module_width,
            'module_height': module_height,
            'font_size': font_size,
            'text_distance': text_distance,
            'quiet_zone': 6.5,
            'write_text': True,
        }

        # 両端に * と、文字間にスペースを入れたフォーマット
        spaced_text = ' '.join(list(clean_data))
        barcode_instance.default_text = f'* {spaced_text} *'

        # SVGデータとしてメモリ上に書き出す
        svg_io = barcode_instance.render(options=options)
        svg_str = svg_io.getvalue().decode('utf-8')

        # StreamlitでSVGを綺麗に画面表示するためのハック
        st.markdown(f'**[{i:03d}] Code: *{spaced_text}***')
        st.image(svg_str.encode('utf-8'), use_container_width=True)

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
