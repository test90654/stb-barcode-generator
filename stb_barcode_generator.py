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

# ReportLab imports for precise PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（印刷用PDF・6個セット版）')
st.write(
    'CSVファイルをアップロードすると、エクセルへの貼り付け不要でそのまま印刷できる「6個セット（縦2×横3）ラベルシートPDF」を一括生成します。'
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

  # 2. 設定項目
  st.subheader('⚙️ バーコード・ラベル設定')
  
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
    font_scale = st.slider(
        '文字の大きさスケール',
        min_value=0.8,
        max_value=1.5,
        value=1.1,
        step=0.05,
    )

  with col2:
    text_distance = st.slider(
        '文字とバーの距離',
        min_value=2.0,
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


  # フォント取得関数
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


  # 1個分のバーコード画像（機種名ヘッダー付き）をPIL Imageとして生成する関数
  def generate_single_barcode_pil(clean_data, model_name, module_width, module_height, font_scale, text_distance):
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'quiet_zone': 6.5,
        'write_text': False,
    }

    rv = io.BytesIO()
    barcode_instance.write(rv, options=options)
    rv.seek(0)

    barcode_img = Image.open(rv).convert('RGB')
    bc_width, bc_height = barcode_img.size

    display_text = f"* {' '.join(list(clean_data))} *"

    # フォントサイズ計算
    optimal_font_size = int((bc_width / (len(display_text) * 1.5)) * font_scale)
    optimal_font_size = max(12, optimal_font_size)
    font = get_proper_font(optimal_font_size)

    dummy_draw = ImageDraw.Draw(barcode_img)
    try:
      char_widths = [dummy_draw.textlength(char, font=font) for char in display_text]
    except AttributeError:
      char_widths = [font.getlength(char) for char in display_text]

    sum_widths = sum(char_widths)
    left_margin = int(bc_width * 0.04)
    right_margin = int(bc_width * 0.04)
    available_width = bc_width - (left_margin + right_margin)

    if len(display_text) > 1:
      spacing = max(1, (available_width - sum_widths) / (len(display_text) - 1))
    else:
      spacing = 0

    # 機種名用ヘッダー高さ ＋ バーコード ＋ 下部テキスト
    header_height = int(optimal_font_size * 1.5)
    padding_bottom = int(optimal_font_size * 1.3 + text_distance)
    
    total_h = bc_height + padding_bottom + header_height
    final_img = Image.new('RGB', (bc_width, total_h), 'white')

    # 機種名（左揃え）を描画
    draw = ImageDraw.Draw(final_img)
    model_font_size = max(10, int(optimal_font_size * 0.9))
    model_font = get_proper_font(model_font_size)
    draw.text((left_margin, 2), model_name, fill='black', font=model_font)

    # バーコード画像を貼り付け（下へずらす）
    final_img.paste(barcode_img, (0, header_height))

    # 下部テキストを描画
    text_y = header_height + bc_height + text_distance
    current_x = left_margin
    for idx, char in enumerate(display_text):
      for dx in [0, 1]:  # 疑似ボールド
        draw.text((current_x + dx, text_y), char, fill='black', font=font)
      current_x += char_widths[idx] + spacing

    return final_img


  # 3. 6個セット（縦2行×横3列）のPDF一括生成処理
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 6個セットラベルシートPDFを一括生成・ダウンロード'):
      pdf_buffer = io.BytesIO()
      
      c = canvas.Canvas(pdf_buffer, pagesize=A4)
      page_width, page_height = A4

      cols = 3
      rows = 2
      
      margin_left = 30 * mm
      margin_top = 30 * mm
      col_gap = 15 * mm
      row_gap = 20 * mm

      cell_w = 50 * mm
      cell_h = 25 * mm

      items_per_page = cols * rows
      current_item_count = 0

      for i, clean_data in enumerate(cleaned_data_list, start=1):
        pil_img = generate_single_barcode_pil(
            clean_data, model_name_input, module_width, module_height, font_scale, text_distance
        )

        temp_img_path = f"temp_bc_{i}.png"
        pil_img.save(temp_img_path, format="PNG")

        slot_idx = current_item_count % items_per_page
        r = slot_idx // cols
        c_idx = slot_idx % cols

        x = margin_left + c_idx * (cell_w + col_gap)
        y = page_height - margin_top - (r + 1) * cell_h - r * row_gap

        c.drawImage(temp_img_path, x, y, width=cell_w, height=cell_h, preserveAspectRatio=True, mask='auto')

        current_item_count += 1

        if os.path.exists(temp_img_path):
          os.remove(temp_img_path)

        if current_item_count % items_per_page == 0 or i == len(cleaned_data_list):
          c.showPage()

      c.save()
      pdf_buffer.seek(0)

      current_date_str = datetime.now().strftime('%Y-%m-%d')
      download_filename = f'stb_barcodes_grid6_{current_date_str}.pdf'

      st.success(f'✨ 全 **{len(cleaned_data_list)}件** のバーコードを6個セット（縦2×横3）のPDFシートにまとめました！')
      st.download_button(
          label='📥 印刷用ラベルシートPDFをダウンロード',
          data=pdf_buffer,
          file_name=download_filename,
          mime='application/pdf',
      )

    # 4. 画面上のプレビュー表示（1個目のサンプル）
    st.markdown('---')
    st.subheader('👀 ラベルプレビュー（1個あたりの見本）')
    if cleaned_data_list:
      sample_data = cleaned_data_list[0]
      sample_pil = generate_single_barcode_pil(
          sample_data, model_name_input, module_width, module_height, font_scale, text_distance
      )
      st.image(sample_pil, caption=f'見本コード: *{sample_data}* (機種名: {model_name_input})')
