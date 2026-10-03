from datetime import datetime
import io
import os
import re
import zipfile
import base64
import barcode
from barcode.writer import SVGWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（機種名表示・確実版）')
st.write(
    'CSVファイル名から機種名を自動抽出し、バーコード上部に左揃えで表示します。'
)

# 1. CSVファイルのアップロード
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  # ファイル名から機種名を自動抽出（例: "TZ-LS200P49台.csv" -> "TZ-LS200P"）
  filename_raw = uploaded_file.name
  extracted_model = "STB-MODEL"
  
  match = re.match(r"^(.+?)(?:\d+台|\d+件|\.csv)", filename_raw)
  if match:
    extracted_model = match.group(1).strip()
  else:
    extracted_model = os.path.splitext(filename_raw)[0]
    extracted_model = re.sub(r'\d+.*$', '', extracted_model).strip()
    if not extracted_model:
      extracted_model = os.path.splitext(filename_raw)[0]

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
      f'✨ CSVから **{len(cleaned_data_list)}件** のデータを読み込みました！（自動抽出された機種名: **{extracted_model}**）'
  )

  # 2. バーコードの設定項目 ＆ 機種名の編集
  st.subheader('⚙️️ バーコード・ラベル設定')
  
  model_name_input = st.text_input(
      'バーコード上に表示する機種名（自動抽出・編集可能）',
      value=extracted_model
  )

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
    letter_spacing = st.slider(
        '文字の間隔 (letter_spacing)',
        min_value=1.0,
        max_value=30.0,
        value=12.0,
        step=1.0,
    )


  # SVGを生成し、機種名と文字間隔を確実に埋め込む関数
  def generate_single_svg_with_model(clean_data, model_name, module_width, module_height, font_size, text_distance, spacing):
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
      # 1. 元のSVGの高さ（height="XX"）の数値部分を抽出して、機種名分の高さ（+22px）を足して書き換える
      height_match = re.search(r'height="([\d\.]+)(?:px)?"', svg_content)
      if height_match:
        orig_h = float(height_match.group(1))
        new_h = orig_h + 22
        svg_content = svg_content.replace(f'height="{height_match.group(1)}"', f'height="{new_h}"')
        # viewBoxも同様に拡張
        viewbox_match = re.search(r'viewBox="0 0 ([\d\.]+) ([\d\.]+)"', svg_content)
        if viewbox_match:
          orig_w = viewbox_match.group(1)
          svg_content = svg_content.replace(viewbox_match.group(0), f'viewBox="0 0 {orig_w} {new_h}"')

      # 2. バーコード全体（rect以外のグループなど）を下に22px移動させるためのグループ変換を挿入
      # <g id="barcode"> 等で囲むか、あるいは直下の要素にtransformを適用
      svg_content = svg_content.replace('<g id="black_bars"', '<g transform="translate(0, 22)" id="black_bars"')

      # 3. 各種テキストの letter-spacing を付与
      svg_content = svg_content.replace('<text ', f'<text style="letter-spacing: {spacing}px;" ')

      # 4. 最上部に機種名テキストを挿入（</svg> の直前に追加）
      if model_name:
        model_svg_tag = f'<text x="10" y="15" style="font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; fill: black;">{model_name}</text>'
        svg_content = svg_content.replace('</svg>', f'{model_svg_tag}</svg>')

    except Exception:
      pass

    return svg_content.encode('utf-8')


  # 3. 一括ZIPダウンロードボタン
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 すべてのバーコードをSVG形式でZIP一括ダウンロード'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, clean_data in enumerate(cleaned_data_list, start=1):
          try:
            svg_bytes = generate_single_svg_with_model(
                clean_data, model_name_input, module_width, module_height, font_size, text_distance, letter_spacing
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
    st.subheader('👀 バーコード一覧プレビュー（機種名入り・1個版）')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        svg_bytes = generate_single_svg_with_model(
            clean_data, model_name_input, module_width, module_height, font_size, text_distance, letter_spacing
        )
        spaced_text = ' '.join(list(clean_data))

        st.markdown(f'**[{i:03d}] Code: *{spaced_text}***')
        
        b64 = base64.b64encode(svg_bytes).decode('utf-8')
        svg_data_url = f'data:image/svg+xml;base64,{b64}'
        st.image(svg_data_url, use_container_width=True)

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
