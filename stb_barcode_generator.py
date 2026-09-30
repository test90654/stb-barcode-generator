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
    '文字の間隔（字間）をバーコードの横幅に合わせてゆったり広げられるプレビューページです。'
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

# 2. バーコード設定（ご指定のバランスを初期値に設定）
st.subheader('⚙️ バーコードの見た目調整')
col1, col2 = st.columns(2)

with col1:
  module_height = st.slider(
      'バーの高さ (module_height)', min_value=5.0, max_value=30.0, value=12.0, step=1.0
  )
  font_size = st.slider(
      '文字の大きさ (font_size)', min_value=6, max_value=24, value=10, step=1
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

# 【追加】文字と文字の間隔（字間）を調整するスライダー
letter_spacing = st.slider(
    '文字の間隔（字間の広がり具合）', min_value=0, max_value=20, value=8, step=1
)

# 3. バーコードの生成とカスタム描画
if target_data:
  try:
    code39 = barcode.get_barcode_class('code39')
    
    # バーコードの図形部分だけを生成（文字は自前で描画するため write_text=False）
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

    # Pillowで画像を読み込み
    base_img = Image.open(rv).convert('RGB')
    draw = ImageDraw.Draw(base_img)
    
    try:
        font = ImageFont.truetype("arial.ttf", size=font_size * 2)
    except IOError:
        font = ImageFont.load_default()

    img_width, img_height = base_img.size
    display_text = target_data

    # 各文字を1文字ずつ配置して、バーコードの横幅全体に広がるように字間を空けて描画する処理
    # まず全文字の合計幅と間隔を計算
    char_widths = []
    total_text_width = 0
    for char in display_text:
        bbox = font.getbbox(char)
        w = bbox[2] - bbox[0]
        char_widths.append(w)
        total_text_width += w

    # 文字間の隙間の数
    num_gaps = len(display_text) - 1
    if num_gaps > 0:
        # スライダーの値（letter_spacing）を反映した総スペース幅
        total_spacing = letter_spacing * num_gaps
        # 開始位置（バーコードの横幅の中央に収まるように計算）
        start_x = (img_width - (total_text_width + total_spacing)) / 2
    else:
        start_x = (img_width - total_text_width) / 2

    # 高さはバーコード下からの距離を考慮
    # フォントの高さを取得
    sample_bbox = font.getbbox("A")
    text_height = sample_bbox[3] - sample_bbox[1]
    text_y = img_height - text_height - text_distance * 2

    # 1文字ずつ間隔を空けながら描画
    current_x = start_x
    for i, char in enumerate(display_text):
        draw.text((current_x, text_y), char, fill="black", font=font)
        current_x += char_widths[i] + letter_spacing

    # 画像を保存
    final_rv = io.BytesIO()
    base_img.save(final_rv, format='PNG')
    final_rv.seek(0)

    st.success('バーコードが生成されました！プレビューをご確認ください。')

    st.image(final_rv, caption=f'Code: {target_data}', use_container_width=True)

    st.download_button(
        label='📥 この画像をダウンロードする',
        data=final_rv,
        file_name=f'stb_barcode_{target_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(f'バーコード生成エラー: {e}')
