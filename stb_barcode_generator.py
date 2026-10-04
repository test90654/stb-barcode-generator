from datetime import datetime
import io
import os
import re
import base64
import barcode
from barcode.writer import SVGWriter
import pandas as pd
import pymupdf
import streamlit as st
import xml.etree.ElementTree as ET
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def register_fonts():
  """リポジトリ同梱のフォントをPDF用に登録（バーコード文字: Arial / 機種名: メイリオ標準）"""
  fonts = {'code': 'Helvetica', 'model': 'Helvetica'}
  try:
    pdfmetrics.registerFont(TTFont('Arial', os.path.join(FONT_DIR, 'ARIAL.TTF')))
    fonts['code'] = 'Arial'
  except Exception:
    pass
  try:
    pdfmetrics.registerFont(
        TTFont('Meiryo', os.path.join(FONT_DIR, 'MEIRYO.TTC'), subfontIndex=0)
    )
    fonts['model'] = 'Meiryo'
  except Exception:
    pass
  return fonts

st.set_page_config(
    page_title='STBバーコード印刷用PDF自動生成ツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード印刷用PDF自動生成ツール（プレビュー対応版）')
st.write(
    'CSVファイルをアップロードすると、プレビューの完璧なSVG品質（美しいフォント・「0」の形状・文字間隔）を100%保ったまま、原本と同じ2×3グリッドのA4印刷用PDFを生成・プレビューできます。'
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

    svg_io = io.BytesIO()
    barcode_instance.write(svg_io, options=options, text=f'*{clean_data}*')
    svg_content = svg_io.getvalue().decode('utf-8')

    try:
      ET.register_namespace('', 'http://www.w3.org/2000/svg')
      root = ET.fromstring(svg_content)
      
      for elem in root.iter():
        if elem.tag.endswith('text'):
          existing_style = elem.get('style', '')
          extra = f"font-family: Arial, Helvetica, sans-serif; letter-spacing: {spacing}px;"
          new_style = f"{existing_style.rstrip(';')}; {extra}" if existing_style else extra
          elem.set('style', new_style)

      svg_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
    except Exception:
      pass

    return svg_content.encode('utf-8')


  # PDF生成ロジックの共通関数
  # svglibはSVGのフォント・letter-spacingを再現できないため、バーと文字をReportLabで直接描画する
  def draw_barcode_cell(c, clean_data, model_name, cell_x, cell_y, cell_w, cell_h, fonts):
    padding = 12
    max_w = cell_w - padding * 2

    # バーコードのモジュール列（スタート/ストップの「*」を含む）
    code39 = barcode.get_barcode_class('code39')
    modules = code39(clean_data, add_checksum=False).build()[0]

    quiet = 6.5 * mm
    bar_unit = module_width * mm
    total_w = len(modules) * bar_unit + quiet * 2
    scale = min(1.0, max_w / total_w)  # セルからはみ出す場合のみ縮小
    bar_unit *= scale
    quiet *= scale
    total_w *= scale
    bar_h = module_height * mm

    # 下の文字（「*データ*」を文字間隔付きで）
    text = f'*{clean_data}*'
    char_space = letter_spacing * 0.75  # px → pt
    glyph_w = pdfmetrics.stringWidth(text, fonts['code'], font_size)
    if len(text) > 1 and glyph_w + char_space * (len(text) - 1) > max_w:
      char_space = max(0.0, (max_w - glyph_w) / (len(text) - 1))
    text_w = glyph_w + char_space * (len(text) - 1)

    name_size = 14
    name_gap = 8
    gap = text_distance * mm * 0.5
    block_h = name_size + name_gap + bar_h + gap + font_size

    # セル内で上下左右中央に配置
    center_x = cell_x + cell_w / 2
    top = cell_y + (cell_h + block_h) / 2

    # バー
    bars_top = top - name_size - name_gap
    x = center_x - total_w / 2 + quiet

    # 機種名（バーコードの左上にそろえる。短いバーコードでセルからはみ出す場合のみ左へずらす）
    name_w = pdfmetrics.stringWidth(model_name, fonts['model'], name_size)
    name_x = max(cell_x + padding, min(x, cell_x + cell_w - padding - name_w))
    c.setFont(fonts['model'], name_size)
    c.drawString(name_x, top - name_size, model_name)
    c.setFillColorRGB(0, 0, 0)
    run_start = None
    for i, m in enumerate(modules + '0'):
      if m == '1' and run_start is None:
        run_start = i
      elif m != '1' and run_start is not None:
        c.rect(x + run_start * bar_unit, bars_top - bar_h,
               (i - run_start) * bar_unit, bar_h, stroke=0, fill=1)
        run_start = None

    # 文字
    c.setFont(fonts['code'], font_size)
    c.drawString(center_x - text_w / 2, bars_top - bar_h - gap - font_size * 0.8,
                 text, charSpace=char_space)

  def create_barcode_pdf(data_list, model_name):
    fonts = register_fonts()
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4

    cols = 2
    rows = 3
    margin_x = 40
    margin_top = 50
    cell_w = (page_width - (margin_x * 2)) / cols
    cell_h = (page_height - (margin_top * 2)) / rows

    for idx, clean_data in enumerate(data_list):
      pos_in_page = idx % 6

      if idx > 0 and pos_in_page == 0:
        c.showPage()

      r = pos_in_page // cols
      col = pos_in_page % cols

      cell_x = margin_x + col * cell_w
      cell_y = page_height - margin_top - (r + 1) * cell_h
      draw_barcode_cell(c, clean_data, model_name, cell_x, cell_y, cell_w, cell_h, fonts)

    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer


  # 3. A4印刷用PDF生成・プレビュー処理
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📄 印刷用PDFを生成・プレビューする'):
      pdf_buffer = create_barcode_pdf(cleaned_data_list, model_name_input)
      
      # セッションステートに保存してブラウザプレビューを維持
      st.session_state['pdf_buffer'] = pdf_buffer.getvalue()
      st.session_state['model_name'] = model_name_input

    # PDFが生成されている場合はブラウザ内でプレビュー表示
    if 'pdf_buffer' in st.session_state:
      st.success('✨ 印刷用PDFの準備ができました！以下のプレビューをご確認ください。')
      
      # ChromeはiframeでのdataURI PDF表示をブロックするため、各ページを画像化して表示する
      pdf_doc = pymupdf.open(stream=st.session_state['pdf_buffer'], filetype='pdf')
      for page_no, page in enumerate(pdf_doc, start=1):
        png_bytes = page.get_pixmap(dpi=120).tobytes('png')
        st.image(png_bytes, caption=f'{page_no} / {pdf_doc.page_count} ページ', use_container_width=True)
      pdf_doc.close()

      date_str = datetime.now().strftime('%Y-%m-%d')
      dl_filename = f'STB_Barcodes_{st.session_state["model_name"]}_{date_str}.pdf'

      st.download_button(
          label='📥 完成版PDFファイルをダウンロード',
          data=st.session_state['pdf_buffer'],
          file_name=dl_filename,
          mime='application/pdf',
      )

    # 4. 個別バーコード一覧プレビュー
    st.markdown('---')
    st.subheader('👀 各バーコードの個別確認')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        svg_bytes = generate_spaced_svg_barcode(
            clean_data, module_width, module_height, font_size, text_distance, letter_spacing
        )
        st.markdown(f'**[{i:03d}] Code:** `*{clean_data}*`')
        
        b64 = base64.b64encode(svg_bytes).decode('utf-8')
        svg_data_url = f'data:image/svg+xml;base64,{b64}'
        st.image(svg_data_url, use_container_width=True)

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
