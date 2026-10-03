from datetime import datetime
import io
import os
import re
import zipfile
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage

st.set_page_config(
    page_title='STBバーコード自動生成・エクセル埋め込みツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード原本自動埋め込みツール')
st.write(
    'CSVファイルと原本エクセルファイルをそれぞれアップロードすると、原本のレイアウトにバーコードを自動配置した完成版エクセルファイルを生成します。'
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
  st.subheader('⚙️ バーコード設定')
  model_name_input = st.text_input(
      'バーコード・エクセル上に表示する機種名（自動抽出・編集可能）',
      value=extracted_model
  )

  # フォント取得ヘルパー
  def get_proper_font(size):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    custom_font = os.path.join(current_dir, 'arial.ttf')
    font_paths = [
        custom_font,
        'C:/Windows/Fonts/meiryo.ttc',
        'C:/Windows/Fonts/YuGothM.ttc',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/Library/Fonts/Arial.ttf'
    ]
    for path in font_paths:
      if os.path.exists(path):
        try:
          return ImageFont.truetype(path, size=int(size))
        except Exception:
          continue
    return ImageFont.load_default()

  # 1個分のラベル画像を生成する関数（機種名＋バーコード＋下部テキスト）
  def generate_single_label_image(clean_data, model_name):
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

    options = {
        'module_width': 0.4,
        'module_height': 12.0,
        'quiet_zone': 8.0,
        'write_text': False,
    }

    rv = io.BytesIO()
    barcode_instance.write(rv, options=options)
    rv.seek(0)

    bc_img = Image.open(rv).convert('RGB')
    bc_w, bc_h = bc_img.size

    display_text = f"* {' '.join(list(clean_data))} *"
    font_size = max(18, int(bc_w * 0.045))
    font = get_proper_font(font_size)

    dummy_draw = ImageDraw.Draw(bc_img)
    try:
      char_widths = [dummy_draw.textlength(char, font=font) for char in display_text]
    except AttributeError:
      char_widths = [font.getlength(char) for char in display_text]

    sum_widths = sum(char_widths)
    left_margin = int(bc_w * 0.03)
    right_margin = int(bc_w * 0.03)
    available_width = bc_w - (left_margin + right_margin)

    if len(display_text) > 1:
      spacing = max(2, (available_width - sum_widths) / (len(display_text) - 1))
    else:
      spacing = 0

    header_h = 42
    footer_h = 35
    total_h = header_h + bc_h + footer_h
    
    label_img = Image.new('RGB', (bc_w, total_h), 'white')
    draw = ImageDraw.Draw(label_img)

    # 機種名（左上・大きくハッキリ）
    model_font_size = max(22, int(bc_w * 0.055))
    model_font = get_proper_font(model_font_size)
    for dx in [0, 1]:
      draw.text((left_margin + dx, 8), model_name, fill='black', font=model_font)

    # バーコード貼り付け
    label_img.paste(bc_img, (0, header_h))

    # 下部テキスト
    text_y = header_h + bc_h + 4
    current_x = left_margin
    for idx, char in enumerate(display_text):
      for dx in [0, 1]:
        draw.text((current_x + dx, text_y), char, fill='black', font=font)
      current_x += char_widths[idx] + spacing

    return label_img


  # 3. エクセル一括生成処理
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 原本エクセルにバーコードを自動埋め込んで生成'):
      if uploaded_excel is None:
        st.error("原本エクセルファイルが選択されていません。上部からアップロードしてください。")
      else:
        # アップロードされたエクセルを読み込み
        wb = openpyxl.load_workbook(uploaded_excel)
        sheet_name = wb.sheetnames[0]
        ws = wb[sheet_name]

        # 原本の配置ルールに基づいてバーコードを埋め込む
        for idx, clean_data in enumerate(cleaned_data_list, start=1):
          # 1個分のバーコード画像を生成
          pil_img = generate_single_label_image(clean_data, model_name_input)
          
          # メモリ上にPNGとして保存
          img_byte_arr = io.BytesIO()
          pil_img.save(img_byte_arr, format='PNG')
          img_byte_arr.seek(0)

          # 5行ごとにブロックが繰り返される構造に対応
          block_row = ((idx - 1) // 2) * 5 + 1
          col_idx = 1 if (idx % 2 != 0) else 7

          # セルに機種名を設定
          ws.cell(row=block_row, column=col_idx).value = model_name_input

          # メモリ上のデータから直接オープンパイジェクセル用画像オブジェクトを作成
          img = OpenpyxlImage(img_byte_arr)
          img.width = 220
          img.height = 80
          
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
