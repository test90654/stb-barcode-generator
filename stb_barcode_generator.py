import io
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成テスト', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード生成・プレビューテスト')
st.write(
    'バーコードの太さと文字の大きさを自由にバランス良く調整できるプレビューページです。'
)

# 1. 入力方法の選択
input_method = st.radio(
    'データの入力方法を選んでください', ('直接入力する', 'CSVファイルから1つ選ぶ')
)

target_data = ''

if input_method == '直接入力する':
  target_data = st.text_input(
      'バーコードにする文字列（例: 19A7B8D90016W）', value='19DDA52A000E'
  )
else:
  uploaded_file = st.file_uploader(
      'テスト用のCSVファイルを選択してください', type=['csv']
  )
  if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    columns = df.columns.tolist()
    target_column = st.selectbox('バーコード化する列を選択:', columns)

    row_index = st.slider('何行目のデータを確認しますか？', 0, len(df) - 1, 0)
    raw_data = df.iloc[row_index][target_column]

    try:
      if isinstance(raw_data, float) or (
          isinstance(raw_data, str) and 'e' in raw_data.lower()
      ):
        target_data = str(int(float(raw_data)))
      else:
        target_data = str(raw_data).strip()
    except Exception:
      target_data = str(raw_data).strip()

    st.write(f'選択されたデータ: **{target_data}**')

# 2. バーコード設定（文字サイズのスライダーの範囲を大きく改善）
st.subheader('⚙️ バーコードの見た目調整')
col1, col2 = st.columns(2)

with col1:
  module_height = st.slider(
      'バーの高さ (module_height)', min_value=5.0, max_value=30.0, value=12.0, step=1.0
  )
  # 【改善】文字サイズを大きくできるように範囲を 10〜40 に拡大（デフォルトも 20 にアップ）
  font_size = st.slider(
      '文字の大きさ (font_size)', min_value=10, max_value=40, value=20, step=1
  )

with col2:
  text_distance = st.slider(
      '文字とバーの距離 (text_distance)',
      min_value=1.0,
      max_value=20.0,
      value=6.0,
      step=1.0,
  )
  module_width = st.slider(
      'バーの太さ (module_width)', min_value=0.1, max_value=1.0, value=0.45, step=0.05
  )

# 3. バーコード生成 ＆ 調整された文字描画
if target_data:
  try:
    code39 = barcode.get_barcode_class('code39')
    
    rv = io.BytesIO()
    barcode_instance = code39(target_data, writer=ImageWriter())

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'quiet_zone': 6.5,
        'write_text': False,
    }

    barcode_instance.write(rv, options=options)
    rv.seek(0)

    # Pillowで画像読み込み
    base_img = Image.open(rv).convert('RGB')
    img_width, img_height = base_img.size

    display_text = f"*{target_data}*"

    # フォントの読み込み（スライダーで大きくしたサイズを反映）
    try:
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except IOError:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(base_img)

    # 各文字の幅を測定
    char_widths = [draw.textlength(char, font=font) for char in display_text]
    total_chars = len(display_text)

    # バーコードの余白に合わせた描画幅の計算
    left_margin = int(img_width * 0.08)
    right_margin = int(img_width * 0.08)
    available_width = img_width - (left_margin + right_margin)

    sum_widths = sum(char_widths)
    if total_chars > 1:
        spacing = (available_width - sum_widths) / (total_chars - 1)
    else:
        spacing = 0

    # 下部の余白を、大きくなったフォントサイズに合わせて自動拡張
    padding_bottom = int(font_size * 1.5 + text_distance)
    new_img = Image.new("RGB", (img_width, img_height + padding_bottom), "white")
    new_img.paste(base_img, (0, 0))
    
    draw_new = ImageDraw.Draw(new_img)
    text_y = img_height + text_distance

    # 1文字ずつ等間隔で描画
    current_x = left_margin
    for i, char in enumerate(display_text):
        draw_new.text((current_x, text_y), char, fill="black", font=font)
        current_x += char_widths[i] + spacing

    final_rv = io.BytesIO()
    new_img.save(final_rv, format='PNG')
    final_rv.seek(0)

    st.success('調整されたバーコードが生成されました！')

    st.image(final_rv, caption=f'Code: {target_data}', use_container_width=True)

    st.download_button(
        label='📥 この画像をダウンロードする',
        data=final_rv,
        file_name=f'stb_barcode_{target_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(f'バーコード生成エラー: {e}')
