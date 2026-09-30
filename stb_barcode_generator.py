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
    'ご提示いただいた画像と同じ「両端のアスタリスク」と「バーコード幅に揃ったゆったりした字間」を完璧に再現するページです。'
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

# 2. バーコード設定
st.subheader('⚙️ バーコードの見た目調整')
col1, col2 = st.columns(2)

with col1:
  module_height = st.slider(
      'バーの高さ (module_height)', min_value=5.0, max_value=30.0, value=12.0, step=1.0
  )
  font_size = st.slider(
      '文字の大きさ (font_size)', min_value=6, max_value=24, value=11, step=1
  )

with col2:
  text_distance = st.slider(
      '文字とバーの距離 (text_distance)',
      min_value=1.0,
      max_value=20.0,
      value=8.0,
      step=1.0,
  )
  module_width = st.slider(
      'バーの太さ (module_width)', min_value=0.1, max_value=1.0, value=0.45, step=0.05
  )

# 3. バーコード生成 ＆ 完璧な文字カスタム描画
if target_data:
  try:
    code39 = barcode.get_barcode_class('code39')
    
    # バーコード本体のみ生成（ライブラリ自体の文字機能は使わない）
    rv = io.BytesIO()
    barcode_instance = code39(target_data, writer=ImageWriter())

    options = {
        'module_width': module_width,
        'module_height': module_height,
        'quiet_zone': 6.5,
        'write_text': False,  # 自前で正確に描画する
    }

    barcode_instance.write(rv, options=options)
    rv.seek(0)

    # Pillowで画像を読み込み
    base_img = Image.open(rv).convert('RGB')
    img_width, img_height = base_img.size

    # バーコードの左右の黒い線の実質的な開始位置と終了位置を割り出すため、
    # Code39の仕様（両端のquiet_zoneを除く）に合わせた描画幅を計算する
    # ※アスタリスクを含めた表示文字列：先頭と末尾に '*' を付与
    display_text = f"*{target_data}*"

    # フォントの読み込み
    try:
        font = ImageFont.truetype("arial.ttf", size=font_size * 2)
    except IOError:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(base_img)

    # 1文字ずつ綺麗に、バーコード全体の横幅いっぱいに等間隔で広がるように配置する計算
    # バーコードの実際の左右の余白（quiet zone）の幅を考慮し、文字がバーコードの幅に綺麗に収まるようにする
    # 両端の文字の中心が、バーコードの左右のバーの端に大体合うように計算します
    
    # フォント描画用の文字ごとの幅を計測
    char_widths = [draw.textlength(char, font=font) for char in display_text]
    total_chars = len(display_text)

    # バーコードの「線の部分」が描かれているおおよその左右の範囲を特定する
    # (quiet_zoneのピクセル数を逆算・推定)
    # python-barcode の quiet_zone=6.5 は通常モジュール幅ベースの余白です
    left_margin = int(img_width * 0.08)   # 左側の余白の目安
    right_margin = int(img_width * 0.08)  # 右側の余白の目安
    available_width = img_width - (left_margin + right_margin)

    # 文字間隔（字間）を自動計算：利用可能な幅の中に全文字が綺麗に等間隔で広がるようにする
    sum_widths = sum(char_widths)
    if total_chars > 1:
        # 字間を自動的に広げて、バーコードの幅に合わせる
        spacing = (available_width - sum_widths) / (total_chars - 1)
    else:
        spacing = 0

    # 画像の下部に文字用の余白（パディング）を拡張する
    padding_bottom = int(font_size * 3.5 + text_distance)
    new_img = Image.new("RGB", (img_width, img_height + padding_bottom), "white")
    new_img.paste(base_img, (0, 0))
    
    draw_new = ImageDraw.Draw(new_img)

    # 文字のY座標（バーコードの下、指定した距離だけ離す）
    text_y = img_height + text_distance

    # 1文字ずつ計算した正確な間隔（spacing）で描画していく
    current_x = left_margin
    for i, char in enumerate(display_text):
        # 各文字を中央揃えっぽく配置するために少し調整しつつ描画
        draw_new.text((current_x, text_y), char, fill="black", font=font)
        current_x += char_widths[i] + spacing

    # 最終的な画像をメモリに保存
    final_rv = io.BytesIO()
    new_img.save(final_rv, format='PNG')
    final_rv.seek(0)

    st.success('理想の形（アスタリスク付き＆幅揃え）でバーコードが生成されました！')

    # 画面プレビュー表示
    st.image(final_rv, caption=f'Code: {target_data}', use_container_width=True)

    # ダウンロードボタン
    st.download_button(
        label='📥 この画像をダウンロードする',
        data=final_rv,
        file_name=f'stb_barcode_{target_data}.png',
        mime='image/png',
    )

  except Exception as e:
    st.error(f'バーコード生成エラー: {e}')
