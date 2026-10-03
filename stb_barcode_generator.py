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
import xml.etree.ElementTree as ET

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（ファイル名自動抽出・6個セット版）')
st.write(
    'CSVファイル名を自動解析して機種名をバーコードに付与し、縦2行×横3列（計6個）のSVGシートを生成します。'
)

# 1. CSVファイルのアップロード
uploaded_file = st.file_uploader(
    'STBリストのCSVファイルを選択してください', type=['csv']
)

if uploaded_file is not None:
  # ファイル名から機種名を自動抽出（例: "TZ-LS200P49台.csv" -> "TZ-LS200P"）
  filename_raw = uploaded_file.name
  extracted_model = "STB-MODEL"
  
  # 「数字や台」の直前までの文字列をモデル名として抽出するパターン
  match = re.match(r"^(.+?)(?:\d+台|\d+件|\.csv)", filename_raw)
  if match:
    extracted_model = match.group(1).strip()
  else:
    # 拡張子を除いた部分をそのまま使う
    extracted_model = os.path.splitext(filename_raw)[0]
    # 末尾の数字などを削る調整
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

  # 2. バーコードの設定項目 ＆ 機種名の編集・確認
  st.subheader('⚙️ バーコード・ラベル設定')
  
  model_name_input = st.text_input(
      'バーコード上に表示する機種名（自動抽出結果・編集可能）',
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


  # 壊れない安全なSVGグリッド生成関数（1個分のSVGを構造解析して正しく3×2にタイリング）
  def generate_grid_svg_barcode(clean_data, model_name, module_width, module_height, font_size, text_distance, spacing):
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
      
      # 1. 文字間隔の最適化
      for elem in root.iter():
        if elem.tag.endswith('text'):
          existing_style = elem.get('style', '')
          new_style = f"{existing_style}; letter-spacing: {spacing}px;" if existing_style else f"letter-spacing: {spacing}px;"
          elem.set('style', new_style)

      # 元のSVGのサイズを取得
      orig_width_str = root.get('width', '200')
      orig_height_str = root.get('height', '50')
      
      orig_w = float(''.join(filter(lambda c: c.isdigit() or c == '.', orig_width_str)))
      orig_height = float(''.join(filter(lambda c: c.isdigit() or c == '.', orig_height_str)))

      # 機種名用ヘッダーの高さ
      header_height = 20
      new_single_h = orig_height + header_height

      # 1個分のパーツを格納するグループ <g> を作成
      single_g = ET.Element('g')

      # 機種名（左揃え）を追加
      if model_name:
        model_text = ET.Element('text')
        model_text.set('x', '10')
        model_text.set('y', '14')
        model_text.set('style', 'font-family: Arial, sans-serif; font-size: 10px; font-weight: bold; fill: black;')
        model_text.text = model_name
        single_g.append(model_text)

      # バーコード本体の要素を下へ移動
      barcode_g = ET.Element('g')
      barcode_g.set('transform', f'translate(0, {header_height})')
      
      # rootの子要素をすべて移行
      for child in list(root):
        root.remove(child)
        barcode_g.append(child)
      
      single_g.append(barcode_g)

      # 2. 縦2行×横3列（計6個）のグリッド全体の寸法計算
      cols = 3
      rows = 2
      margin_x = 15
      margin_y = 15

      total_w = cols * orig_w + (cols - 1) * margin_x
      total_h = rows * new_single_h + (rows - 1) * margin_y

      # 新しい親SVGコンテナを作成
      parent_svg = ET.Element('svg')
      parent_svg.set('xmlns', 'http://www.w3.org/2000/svg')
      parent_svg.set('width', f'{total_w}')
      parent_svg.set('height', f'{total_h}')
      parent_svg.set('viewBox', f'0 0 {total_w} {total_h}')
      
      # 背景を白に設定
      bg_rect = ET.Element('rect')
      bg_rect.set('width', '100%')
      bg_rect.set('height', '100%')
      bg_rect.set('fill', 'white')
      parent_svg.append(bg_rect)

      # 3×2の各セルに配置
      for r in range(rows):
        for c in range(cols):
          x_offset = c * (orig_w + margin_x)
          y_offset = r * (new_single_h + margin_y)

          cell_g = ET.Element('g')
          cell_g.set('transform', f'translate({x_offset}, {y_offset})')
          
          # 独立したコピーとして追加
          cell_elem = ET.fromstring(ET.tostring(single_g, encoding='utf-8'))
          cell_g.append(cell_elem)
          
          parent_svg.append(cell_g)

      svg_content = ET.tostring(parent_svg, encoding='utf-8').decode('utf-8')
    except Exception:
      pass

    return svg_content.encode('utf-8')


  # 3. 一括ZIPダウンロードボタン（SVG形式）
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 すべての6個セットバーコードをSVG形式でZIP一括ダウンロード'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, clean_data in enumerate(cleaned_data_list, start=1):
          try:
            svg_bytes = generate_grid_svg_barcode(
                clean_data, model_name_input, module_width, module_height, font_size, text_distance, letter_spacing
            )
            filename = f'{i:03d}_stb_barcode_{clean_data}_grid6.svg'
            zip_file.writestr(filename, svg_bytes)
            success_count += 1
          except Exception:
            pass

      if success_count > 0:
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        download_filename = f'stb_barcodes_grid6_svg_{current_date_str}.zip'

        st.success(f'✨ {success_count}件の6個セットSVGバーコードZIP作成が完了しました！')
        zip_buffer.seek(0)
        st.download_button(
            label='📥 6個セットSVGバーコードZIPをダウンロード',
            data=zip_buffer,
            file_name=download_filename,
            mime='application/zip',
        )

    # 4. 画面上のプレビュー一覧表示
    st.markdown('---')
    st.subheader('👀 バーコード一覧プレビュー（縦2行×横3列・6個セット）')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        svg_bytes = generate_grid_svg_barcode(
            clean_data, model_name_input, module_width, module_height, font_size, text_distance, letter_spacing
        )
        spaced_text = ' '.join(list(clean_data))

        st.markdown(f'**[{i:03d}] Code: *{spaced_text}*** (機種名: {model_name_input})')
        
        b64 = base64.b64encode(svg_bytes).decode('utf-8')
        svg_data_url = f'data:image/svg+xml;base64,{b64}'
        st.image(svg_data_url, use_container_width=True)

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
