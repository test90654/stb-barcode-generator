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

# ReportLab for print-ready A4 6-item grid PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（機種名視認性大幅改善版）')
st.write(
    '機種名を大きくハッキリと表示し、A4用紙に6個セット（縦2×横3）で印刷できるPDFを一括生成します。'
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
        value=12.0,
        step=1.0,
    )
  with col2:
    module_width = st.slider(
        'バーの太さ (module_width)',
        min_value=0.2,
        max_value=1.0,
        value=0.4,
        step=0.05,
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


  # 1個分のラベル画像を生成する関数（機種名をしっかり大きく視認性高く配置）
  def generate_single_label_image(clean_data, model_name, module_width, module_height):
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'quiet_zone': 6.5,
        'write_text': True,  # 下部の数字は既存の美しいレイアウトを維持
        'font_size': 11,
        'text_distance': 5.0,
    }

    rv = io.BytesIO()
    barcode_instance.write(rv, options=options)
    rv.seek(0)

    bc_img = Image.open(rv).convert('RGB')
    bc_w, bc_h = bc_img.size

    # 【改善】機種名用ヘッダー領域を十分に大きく確保（高さ45px）
    header_h = 45
    total_h = bc_h + header_h

    label_img = Image.new('RGB', (bc_w, total_h), 'white')

    # 機種名を大きくハッキリと左上に描画
    draw = ImageDraw.Draw(label_img)
    
    # フォントサイズをバーコード幅に対して十分に大きく設定（例: 幅の約7%、最低26px以上）
    model_font_size = max(26, int(bc_w * 0.07))
    font = get_proper_font(model_font_size)
    
    # 太字っぽく描画するために数ピクセルずらして重ね描き
    left_margin = int(bc_w * 0.03)
    for dx in [0, 1]:
      draw.text((left_margin + dx, 8), model_name, fill='black', font=font)

    # バーコード本体を下に貼り付け
    label_img.paste(bc_img, (0, header_h))

    return label_img


  # 3. PDF一括生成（6個セットシート）
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 6個セットラベルシート（PDF）を一括生成・ダウンロード'):
      pdf_buffer = io.BytesIO()
      c = canvas.Canvas(pdf_buffer, pagesize=A4)
      page_w, page_h = A4

      cols = 3
      rows = 2
      
      margin_left = 20 * mm
      margin_top = 25 * mm
      col_gap = 10 * mm
      row_gap = 15 * mm

      cell_w = 55 * mm
      cell_h = 32 * mm

      items_per_page = cols * rows
      count = 0

      for i, clean_data in enumerate(cleaned_data_list, start=1):
        label_pil = generate_single_label_image(
            clean_data, model_name_input, module_width, module_height
        )

        temp_path = f"temp_label_{i}.png"
        label_pil.save(temp_path, format="PNG")

        slot = count % items_per_page
        r = slot // cols
        cl = slot % cols

        x = margin_left + cl * (cell_w + col_gap)
        y = page_h - margin_top - (r + 1) * cell_h - r * row_gap

        c.drawImage(temp_path, x, y, width=cell_w, height=cell_h, preserveAspectRatio=True, mask='auto')

        count += 1
        if os.path.exists(temp_path):
          os.remove(temp_path)

        if count % items_per_page == 0 or i == len(cleaned_data_list):
          c.showPage()

      c.save()
      pdf_buffer.seek(0)

      date_str = datetime.now().strftime('%Y-%m-%d')
      dl_name = f'stb_barcodes_grid6_{date_str}.pdf'

      st.success(f'✨ 全 {len(cleaned_data_list)}件のバーコードを6個セットPDFシートにまとめました！')
      st.download_button(
          label='📥 印刷用ラベルシートPDFをダウンロード',
          data=pdf_buffer,
          file_name=dl_name,
          mime='application/pdf',
      )

    # 4. プレビュー表示
    st.markdown('---')
    st.subheader('👀 ラベルプレビュー（1個あたりの見本）')
    if cleaned_data_list:
      sample_data = cleaned_data_list[0]
      sample_pil = generate_single_label_image(
          sample_data, model_name_input, module_width, module_height
      )
      st.image(sample_pil, caption=f'見本: *{sample_data}* (機種名: {model_name_input})', width=450)
