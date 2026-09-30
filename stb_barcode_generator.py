from datetime import datetime
import io
import os
import zipfile
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（フォント確実適用版）')
st.write(
    'CSVファイル（A列）をアップロードすると、文字サイズを自由に変更して綺麗なバーコードを作成できます。'
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
        min_value=20.0,
        max_value=120.0,
        value=60.0,
        step=5.0,
    )
    font_size = st.slider(
        '文字の大きさ (font_size)',
        min_value=12,
        max_value=60,
        value=28,
        step=2,
    )

  with col2:
    text_distance = st.slider(
        '文字とバーの距離 (text_distance)',
        min_value=2.0,
        max_value=40.0,
        value=12.0,
        step=2.0,
    )
    module_width = st.slider(
        'バーの太さ (module_width)', min_value=0.2, max_value=1.5, value=0.5, step=0.1
    )


  # フォントを確実にロードするヘルパー関数
  def get_proper_font(size):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    custom_font = os.path.join(current_dir, 'arial.ttf')

    font_paths = [
        custom_font,
        'C:/Windows/Fonts/meiryo.ttc',
        'C:/Windows/Fonts/YuGothM.ttc',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux/Cloud用
        '/Library/Fonts/Arial.ttf'  # Mac用
    ]

    for path in font_paths:
      if os.path.exists(path):
        try:
          return ImageFont.truetype(path, size=size)
        except Exception:
          continue
    
    # 万が一どのTrueTypeフォントも見つからない場合のエラー防止
    return ImageFont.load_default()


  # バーコード画像生成関数
  def generate_perfect_barcode_image(clean_data, module_width, module_height, font_size, text_distance):
    code39 = barcode.get_barcode_class('code39')
    barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'quiet_zone': 10.0,
        'write_text': False,
    }

    rv = io.BytesIO()
    barcode_instance.write(rv, options=options)
    rv.seek(0)

    barcode_img = Image.open(rv).convert('RGB')
    bc_width, bc_height = barcode_img.size

    display_text = f"* {' '.join(list(clean_data))} *"

    # 確実にサイズ変更が効くフォントを取得
    font = get_proper_font(font_size)

    dummy_draw = ImageDraw.Draw(barcode_img)
    char_widths = [dummy_draw.textlength(char, font=font) for char in display_text]
    sum_widths = sum(char_widths)

    left_margin = int(bc_width * 0.03)
    right_margin = int(bc_width * 0.03)
    available_width = bc_width - (left_margin + right_margin)

    if len(display_text) > 1:
      spacing = max(2, (available_width - sum_widths) / (len(display_text) - 1))
    else:
      spacing = 0

    padding_bottom = int(font_size * 1.5 + text_distance)
    final_img = Image.new('RGB', (bc_width, bc_height + padding_bottom), 'white')
    final_img.paste(barcode_img, (0, 0))

    draw = ImageDraw.Draw(final_img)
    text_y = bc_height + text_distance

    current_x = left_margin
    for idx, char in enumerate(display_text):
      draw.text((current_x, text_y), char, fill='black', font=font)
      current_x += char_widths[idx] + spacing

    out_rv = io.BytesIO()
    final_img.save(out_rv, format='PNG')
    out_rv.seek(0)
    return out_rv


  # 3. 一括ZIPダウンロードボタン
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 すべてのバーコード画像をPNG形式でZIP一括ダウンロード'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, clean_data in enumerate(cleaned_data_list, start=1):
          try:
            img_rv = generate_perfect_barcode_image(
                clean_data, module_width, module_height, font_size, text_distance
            )
            filename = f'{i:03d}_stb_barcode_{clean_data}.png'
            zip_file.writestr(filename, img_rv.getvalue())
            success_count += 1
          except Exception:
            pass

      if success_count > 0:
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        download_filename = f'stb_barcodes_png_{current_date_str}.zip'

        st.success(f'✨ {success_count}件のバーコードZIP作成が完了しました！')
        zip_buffer.seek(0)
        st.download_button(
            label='📥 バーコードZIPをダウンロード',
            data=zip_buffer,
            file_name=download_filename,
            mime='application/zip',
        )

    # 4. 画面上のプレビュー一覧表示
    st.markdown('---')
    st.subheader('👀 バーコード一覧プレビュー')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        img_rv = generate_perfect_barcode_image(
            clean_data, module_width, module_height, font_size, text_distance
        )
        spaced_text = ' '.join(list(clean_data))
        st.image(
            img_rv,
            caption=f'[{i:03d}] Code: *{spaced_text}*',
            use_container_width=True,
        )
      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
