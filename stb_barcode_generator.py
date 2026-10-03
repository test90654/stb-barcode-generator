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
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

st.set_page_config(
    page_title='STBバーコード印刷用PDF自動生成ツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード印刷用PDF自動生成ツール（ベクター品質版）')
st.write(
    'CSVファイルをアップロードすると、プレビューの完璧なSVG品質（美しいフォント・「0」の形状・文字間隔）を100%保ったまま、原本と同じ2×3グリッドのA4印刷用PDFを一発生成します。'
)

# 1. CSVファイルのアップロード
uploaded_csv = st.file_uploader(
    '1. STBリストのCSVファイルを選択してください', type=['csv']
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
    
    letter_spacing = st.slider(
        '文字の間隔 (letter_spacing)',
        min_value=1.0,
        max_value=30.0,
        value=12.0,
        step=1.0,
    )

  model_name_input = st.text_input(
      '印刷シート上に表示する機種名（自動抽出・編集可能）',
      value=extracted_model
  )


  # プレビューおよびPDF用の完璧なSVGバーコードを生成する関数
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


  # 3. A4印刷用PDF一括生成処理（2×3グリッド構造）
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📄 完璧なSVG品質の印刷用PDFを一発生成'):
      pdf_buffer = io.BytesIO()
      # A4サイズ縦向き
      c = canvas.Canvas(pdf_buffer, pagesize=A4)
      page_width, page_height = A4

      # 1ページあたり6個（2列×3行）のレイアウト配置設定
      cols = 2
      rows = 3
      margin_x = 40
      margin_top = 50
      cell_w = (page_width - (margin_x * 2)) / cols
      cell_h = (page_height - (margin_top * 2)) / rows

      for idx, clean_data in enumerate(cleaned_data_list):
        page_idx = idx // 6
        pos_in_page = idx % 6

        if idx > 0 and pos_in_page == 0:
          c.showPage()  # 6個溜まったら次のページへ

        # ページ内での行・列インデックス（2列×3行）
        r = pos_in_page // cols
        col = pos_in_page % cols

        x = margin_x + col * cell_w + 20
        # 上から順に配置していく座標計算
        y = page_height - margin_top - (r + 1) * cell_h + 30

        # 機種名を上部に描画
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, y + 60, model_name_input)

        # SVGバーコードを生成し、ReportLabのDrawingオブジェクトに変換して埋め込み
        svg_bytes = generate_spaced_svg_barcode(
            clean_data, module_width, module_height, font_size, text_distance, letter_spacing
        )
        
        svg_io = io.BytesIO(svg_bytes)
        try:
          drawing = svg2rlg(svg_io)
          if drawing:
            # 適切なサイズにスケーリングして描画
            drawing.width = 240
            drawing.height = 50
            drawing.hAlign = 'LEFT'
            renderPDF.draw(drawing, c, x, y)
        except Exception:
          pass

      c.save()
      pdf_buffer.seek(0)

      date_str = datetime.now().strftime('%Y-%m-%d')
      dl_filename = f'STB_Barcodes_{model_name_input}_{date_str}.pdf'

      st.success(f'✨ 全 {len(cleaned_data_list)}件のバーコードを収めた印刷用PDFを生成しました！')
      st.download_button(
          label='📥 印刷用PDFファイルをダウンロード',
          data=pdf_buffer,
          file_name=dl_filename,
          mime='application/pdf',
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
