from datetime import datetime
import io
import zipfile
import barcode
from barcode.writer import ImageWriter
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title='STBバーコード生成・プレビューツール', page_icon='📦', layout='centered'
)

st.title('📦 STBバーコード生成・プレビューツール（PNG版）')
st.write(
    'CSVファイル（A列）をアップロードすると、画面上でPNG形式のプレビュー確認と、ZIPでの一括ダウンロードが行えます。'
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
        '文字の大きさ (font_size)', min_value=6, max_value=24, value=10, step=1
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

  # 共通のバーコード生成オプション
  options = {
      'module_width': module_width,
      'module_height': module_height,
      'font_size': font_size,
      'text_distance': text_distance,
      'quiet_zone': 6.5,
      'write_text': True,
  }

  # 3. 一括ZIPダウンロードボタン
  st.markdown('---')
  if cleaned_data_list:
    if st.button('📦 すべてのバーコード画像をPNG形式でZIP一括ダウンロード'):
      zip_buffer = io.BytesIO()
      success_count = 0

      with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, clean_data in enumerate(cleaned_data_list, start=1):
          try:
            code39 = barcode.get_barcode_class('code39')
            # add_checksum=False で余計な文字の追加を防止
            barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

            spaced_text = ' '.join(list(clean_data))
            barcode_instance.default_text = f'* {spaced_text} *'

            rv = io.BytesIO()
            barcode_instance.write(rv, options=options)
            
            # 3桁連番付きファイル名でZIPに格納（CSVの並び順を完全維持）
            filename = f'{i:03d}_stb_barcode_{clean_data}.png'
            zip_file.writestr(filename, rv.getvalue())
            success_count += 1
          except Exception:
            pass

      if success_count > 0:
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        download_filename = f'stb_barcodes_png_{current_date_str}.zip'

        st.success(f'✨ {success_count}件のPNGバーコードのZIP作成が完了しました！')
        zip_buffer.seek(0)
        st.download_button(
            label='📥 PNGバーコードZIPをダウンロード',
            data=zip_buffer,
            file_name=download_filename,
            mime='application/zip',
        )

    # 4. 画面上のプレビュー一覧表示（PNG形式）
    st.markdown('---')
    st.subheader('👀 バーコード一覧プレビュー')

    for i, clean_data in enumerate(cleaned_data_list, start=1):
      try:
        code39 = barcode.get_barcode_class('code39')
        barcode_instance = code39(clean_data, writer=ImageWriter(), add_checksum=False)

        spaced_text = ' '.join(list(clean_data))
        barcode_instance.default_text = f'* {spaced_text} *'

        rv = io.BytesIO()
        barcode_instance.write(rv, options=options)
        rv.seek(0)

        st.image(
            rv,
            caption=f'[{i:03d}] Code: *{spaced_text}*',
            use_container_width=True,
        )

      except Exception as e:
        st.error(f'プレビュー生成エラー ({clean_data}): {e}')
