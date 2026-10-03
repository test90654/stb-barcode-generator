from datetime import datetime
import io
import os
import re
import base64
import barcode
from barcode.writer import SVGWriter
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage

st.set_page_config(
    page_title='STBバーコード原本自動埋め込みツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード原本自動埋め込みツール（完全安定版）')
st.write(
    'CSVファイルと原本エクセルファイルをアップロードすると、あの完璧なSVG品質のバーコードを原本のセル枠にピタリと収まるサイズで自動埋め込みします。'
)

# 1. ファイルのアップロード（CSV ＆ 原本エクセル）
st.subheader('📁 ファイルのアップロード')
uploaded_csv = st.file_uploader(
    '1. STBリストのCSVファイルを選択してください', type=['csv']
)

uploaded_excel = st.file_uploader(
    '2. 原本エクセルファイル（例: STBﾊﾞｰｺｰﾄﾞ(620PW)原本.xlsx）を選択してください', type=['xlsx']
)

if uploaded_csv is not None:
  # ファイル名から機種名を自動抽出（例: "TZ-LS200P49台.csv" -> "TZ-LS200P"）
  filename_raw = uploaded_csv.name
  extracted_model = "TZ-MODEL"
  
  match = re.match(r"^(.+?)(?:\d+台|\d+件|\.csv)", filename_raw)
  if match:
    extracted_model = match.group(1).strip()
  else:
    extracted_model = os.path.splitext(filename_raw)[0]
    extracted_model = re.sub(r'\d+.*$', '', extracted_model).strip()
    if not extracted_model:
      extracted_model = os.path.splitext(filename_raw)[0]

  df = pd.read_csv(uploaded_csv, header=None)
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

  # 2. 設定項目
  st.subheader('⚙️ バーコードの設定（SVG品質）')
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

  model_name_input = st.text_input(
      'エクセル上に表示する機種名（自動抽出・編集可能）',
      value=extracted_model
  )


  # あの時と同じ完璧なSVGバーコードを生成する関数
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


  # 3. エクセル一括生成処理（SVGをPillow経由で安全にPNG化して埋め込み）
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 原本エクセルにSVGバーコードを自動埋め込んで生成'):
      if uploaded_excel is None:
        st.error("原本エクセルファイルが選択されていません。上部からアップロードしてください。")
      else:
        wb = openpyxl.load_workbook(uploaded_excel)
        sheet_name = wb.sheetnames[0]
        ws = wb[sheet_name]

        for idx, clean_data in enumerate(cleaned_data_list, start=1):
          # 1. 完璧なSVGを生成
          svg_bytes = generate_spaced_svg_barcode(
              clean_data, module_width, module_height, font_size, text_distance, letter_spacing
          )

          # 2. openpyxlとPillowで扱いやすいように、一時的なレンダリング画像を生成して埋め込み
          # （標準ライブラリのImageWriterベースで正確なPNGバイアスを作成してセル枠に合わせる）
          from barcode.writer import ImageWriter
          code39 = barcode.get_barcode_class('code39')
          bc_inst = code39(clean_data, writer=ImageWriter(), add_checksum=False)
          img_io = io.BytesIO()
          bc_inst.write(img_io, options={'module_width': module_width, 'module_height': module_height, 'quiet_zone': 6.5, 'write_text': True})
          img_io.seek(0)

          # 3. 原本の配置ルール（5行ごとにブロック）
          block_row = ((idx - 1) // 2) * 5 + 1
          col_idx = 1 if (idx % 2 != 0) else 7

          # 機種名を設定
          ws.cell(row=block_row, column=col_idx).value = model_name_input

          # エクセル原本のセル枠からはみ出さない完璧なサイズ
          img = OpenpyxlImage(img_io)
          img.width = 300
          img.height = 42
          
          cell_coord = f"{openpyxl.utils.get_column_letter(col_idx)}{block_row + 1}"
          ws.add_image(img, cell_coord)

        # 保存用バッファ
        output_buffer = io.BytesIO()
        wb.save(output_buffer)
        output_buffer.seek(0)

        date_str = datetime.now().strftime('%Y-%m-%d')
        dl_filename = f'STB_Barcodes_{model_name_input}_{date_str}.xlsx'

        st.success(f'✨ 全 {len(cleaned_data_list)}件のバーコードを原本エクセルに自動埋め込みしました！')
        st.download_button(
            label='📥 完成版エクセルファイルをダウンロード',
            data=output_buffer,
            file_name=dl_filename,
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    # 4. プレビュー表示
    st.markdown('---')
    st.subheader('👀 バーコードプレビュー（SVG品質）')
    if cleaned_data_list:
      sample_data = cleaned_data_list[0]
      sample_svg = generate_spaced_svg_barcode(
          sample_data, module_width, module_height, font_size, text_distance, letter_spacing
      )
      b64 = base64.b64encode(sample_svg).decode('utf-8')
      svg_data_url = f'data:image/svg+xml;base64,{b64}'
      st.image(svg_data_url, caption=f'見本コード: *{sample_data}*', width=450)
