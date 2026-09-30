from datetime import datetime
import io
import os
import zipfile
import base64
import barcode
from barcode.writer import SVGWriter
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（文字間隔広範囲対応版）')
st.write(
    'CSVファイル（A列）をアップロードすると、文字間隔を大きく広げてバーコード幅に最適化できるSVGバーコードをプレビュー・ZIPダウンロードできます。'
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
        value=9.0,
        step=1.0,
    )
    font_size = st.slider(
        '文字の大きさ (font_size)',
        min_value=8,
        max_value=24,
        value=12,
        step=1,
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
        'バーの太さ (module_width)',
        min_value=0.1,
        max_value=1.0,
        value=0.4,
        step=0.05,
    )
    
    # 【上限を30.0に拡張】文字の間隔をしっかり広く調整できるように変更
    letter_spacing = st.slider(
        '文字の間隔 (letter_spacing)',
        min_value=1.0,
        max_value=30.0,
        value=12.0,  # 理想の間隔を探しやすいようデフォルトも12.0に引き上げ
        step=1.0,
    )


  # XMLパースを用いて文字間隔を拡張するSVG生成関数
  def generate_spaced_svg_barcode(clean_data, module_width, module_height, font_size, text_distance, spacing):
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=SVGWriter(), add_checksum=False)

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'font_size': font_size,
        'text_distance': text_distance,
        'quiet_zone': 6.5,
        'write_text': True,
    }

    spaced_text = ' '.join(list(clean_data))
    barcode_instance.default_text = f'* {spaced_text} *'

    svg_io = io.BytesIO()
    barcode_instance.write(svg_io, options=options)
    svg_content = svg_io.getvalue().decode('utf-8')

    try:
      ET.register_namespace('', 'http://www.w3.org/2000/svg')
      root = ET.fromstring(svg_content)
      
      for elem in root.iter():
        if elem.tag.endswith('text'):
          existing_style = elem.get('style', '')
          new_style = f"{existing_style}; letter-spacing: {spacing}px;" if existing_style else f"letter-spacing: {spacing}px;"
          elem.set('style', new_style)

      svg_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
    except Exception:
      pass

    return svg_content.encode('utf-8')


  # 3. 一括ZIPダウンロードボタン（SVG形式）
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 すべてのバーコード画像をSVG形式でZIP一括ダウンロード'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, clean_data in enumerate(cleaned_data_list, start=1):
          try:
            svg_bytes = generate_spaced_svg_barcode(
                clean_data, module_width, module_height, font_size, text_distance, letter_spacing
            )
            filename = f'{i:03d}_stb_barcode_{clean_data}.svg'
            zip_file.writestr(filename, svg_bytes)
            success_count += 1
          except Exception:
            pass

      if success_count > 0:
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        download_filename = f'stb_barcodes_svg_{current_date_str}.zip'

        st.success(f'✨ {success_count}件のSVGバーコードZIP作成が完了しました！')
        zip_buffer.seek(0)
        st.download_button(
            label='📥 SVGバーコードZIPをダウンロード',
            data=zip_buffer,
            file_name=download_filename,
            mime='application/zip',
        )

    # 4. 画面上のプレビュー一覧表示
    st.markdown('---')
    st.subheader('👀 バーコード一覧プレビュー')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        svg_bytes = generate_spaced_svg_barcode(
            clean_data, module_width, module_height, font_size, text_distance, letter_spacing
        )
        spaced_text = ' '.join(list(clean_data))

        st.markdown(f'**[{i:03d}] Code: *{spaced_text}***')
        
        b64 = base64.b64encode(svg_bytes).decode('utf-8')
        svg_data_url = f'data:image/svg+xml;base64,{b64}'
        st.image(svg_data_url, use_container_width=True)

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
