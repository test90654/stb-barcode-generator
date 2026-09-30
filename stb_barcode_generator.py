import io
import os
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコードプレビューツール', page_icon='🔍', layout='centered'
)

st.title('🔍 STBバーコード・画面プレビューツール')
st.write(
    'CSVファイル（A列に管理番号等が入ったファイル）をアップロードすると、画面上で直接すべてのバーコードの見た目を確認できます。'
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
        min_value=5.0,
        max_value=30.0,
        value=15.0,
        step=1.0,
    )
    font_size = st.slider(
        '文字の大きさ (font_size)', min_value=6, max_value=24, value=12, step=1
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
        'バーの太さ (module_width)', min_value=0.1, max_value=1.0, value=0.3, step=0.05
    )

  # 3. 画面上のプレビュー一覧表示（完全自前描画で形と字間・0の形を正常化）
  st.markdown('---')
  st.subheader('👀 バーコード一覧プレビュー')

  if cleaned_data_list:
    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        code39 = barcode.get_barcode_class('code39')
        # 【重要】ライブラリ側の文字描画は使わず、バーコードの図形だけを生成する
        barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

        options = {
            'module_width': module_width,
            'module_height': module_height,
            'quiet_zone': 6.5,
            'write_text': False,  # 文字は自前で描画するためオフ
        }

        rv = io.BytesIO()
        barcode_instance.write(rv, options=options)
        rv.seek(0)

        # Pillowで画像を読み込み
        base_img = Image.open(rv).convert('RGB')
        img_width, img_height = base_img.size

        # 両端にアスタリスク、文字の間にスペースを入れた文字列を定義
        display_text = f"* {' '.join(list(clean_data))} *"

        # フォントの読み込み（Windows標準の綺麗なゴシックやメイリオ、またはデフォルト）
        font = None
        current_dir = os.path.dirname(os.path.abspath(__file__))
        custom_font = os.path.join(current_dir, 'arial.ttf')
        
        try:
            if os.path.exists(custom_font):
                font = ImageFont.truetype(custom_font, size=font_size * 2)
            elif os.path.exists('C:/Windows/Fonts/meiryo.ttc'):
                font = ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc', size=font_size * 2)
            elif os.path.exists('C:/Windows/Fonts/YuGothM.ttc'):
                font = ImageFont.truetype('C:/Windows/Fonts/YuGothM.ttc', size=font_size * 2)
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(base_img)

        # 各文字の幅を測定し、バーコードの横幅いっぱいに綺麗に等間隔で並べる
        char_widths = [draw.textlength(char, font=font) for char in display_text]
        total_chars = len(display_text)

        left_margin = int(img_width * 0.08)
        right_margin = int(img_width * 0.08)
        available_width = img_width - (left_margin + right_margin)

        sum_widths = sum(char_widths)
        if total_chars > 1:
            spacing = (available_width - sum_widths) / (total_chars - 1)
        else:
            spacing = 0

        # 下部に文字用の余白（パディング）を拡張
        padding_bottom = int(font_size * 2.5 + text_distance)
        new_img = Image.new("RGB", (img_width, img_height + padding_bottom), "white")
        new_img.paste(base_img, (0, 0))
        
        draw_new = ImageDraw.Draw(new_img)
        text_y = img_height + text_distance

        # 1文字ずつ等間隔で描画（変形やドットのない正常な「0」を維持）
        current_x = left_margin
        for idx, char in enumerate(display_text):
            draw_new.text((current_x, text_y), char, fill="black", font=font)
            current_x += char_widths[idx] + spacing

        final_rv = io.BytesIO()
        new_img.save(final_rv, format='PNG')
        final_rv.seek(0)

        # 画面に順番通りに画像を表示
        st.image(
            final_rv,
            caption=f'[{i:03d}] Code: {display_text}',
            use_container_width=True,
        )
      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
