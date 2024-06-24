import json
import os
import sys
import shutil
import urllib.request
import zipfile
from argparse import ArgumentParser

import gradio as gr

sys.path.append('/content/CoverGen/_CoverGen')
from src.main import song_cover_pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mdxnet_models_dir = os.path.join(BASE_DIR, 'mdxnet_models')
rvc_models_dir = os.path.join(BASE_DIR, 'rvc_models')
output_dir = os.path.join(BASE_DIR, 'song_output')
image_path = "/content/CoverGen/content/CoverGen.png"

def get_current_models(models_dir):
    models_list = os.listdir(models_dir)
    items_to_remove = ['hubert_base.pt', 'MODELS.txt', 'public_models.json', 'rmvpe.pt']
    return [item for item in models_list if item not in items_to_remove]

def update_models_list():
    models_l = get_current_models(rvc_models_dir)
    return gr.Dropdown.update(choices=models_l)

def extract_zip(extraction_folder, zip_name):
    os.makedirs(extraction_folder)
    with zipfile.ZipFile(zip_name, 'r') as zip_ref:
        zip_ref.extractall(extraction_folder)
    os.remove(zip_name)

    index_filepath, model_filepath = None, None
    for root, dirs, files in os.walk(extraction_folder):
        for name in files:
            if name.endswith('.index') and os.stat(os.path.join(root, name)).st_size > 1024 * 100:
                index_filepath = os.path.join(root, name)

            if name.endswith('.pth') and os.stat(os.path.join(root, name)).st_size > 1024 * 1024 * 40:
                model_filepath = os.path.join(root, name)

    if not model_filepath:
        raise gr.Error(f'Не найден файл модели .pth в распакованном zip-файле. Пожалуйста, проверьте {extraction_folder}.')

    os.rename(model_filepath, os.path.join(extraction_folder, os.path.basename(model_filepath)))
    if index_filepath:
        os.rename(index_filepath, os.path.join(extraction_folder, os.path.basename(index_filepath)))

    for filepath in os.listdir(extraction_folder):
        if os.path.isdir(os.path.join(extraction_folder, filepath)):
            shutil.rmtree(os.path.join(extraction_folder, filepath))

def download_online_model(url, dir_name, progress=gr.Progress()):
    try:
        progress(0, desc=f'[~] Загрузка голосовой модели с именем {dir_name}...')
        zip_name = url.split('/')[-1]
        extraction_folder = os.path.join(rvc_models_dir, dir_name)
        if os.path.exists(extraction_folder):
            raise gr.Error(f'Директория голосовой модели {dir_name} уже существует! Выберите другое имя для вашей голосовой модели.')

        if 'pixeldrain.com' in url:
            url = f'https://pixeldrain.com/api/file/{zip_name}'

        urllib.request.urlretrieve(url, zip_name)

        progress(0.5, desc='[~] Распаковка zip-файла...')
        extract_zip(extraction_folder, zip_name)
        return f'[+] Модель {dir_name} успешно загружена!'

    except Exception as e:
        raise gr.Error(str(e))

def upload_local_model(zip_path, dir_name, progress=gr.Progress()):
    try:
        extraction_folder = os.path.join(rvc_models_dir, dir_name)
        if os.path.exists(extraction_folder):
            raise gr.Error(f'Директория голосовой модели {dir_name} уже существует! Выберите другое имя для вашей голосовой модели.')

        zip_name = zip_path.name
        progress(0.5, desc='[~] Распаковка zip-файла...')
        extract_zip(extraction_folder, zip_name)
        return f'[+] Модель {dir_name} успешно загружена!'

    except Exception as e:
        raise gr.Error(str(e))

def pub_dl_autofill(pub_models, event: gr.SelectData):
    return gr.Text.update(value=pub_models.loc[event.index[0], 'URL']), gr.Text.update(value=pub_models.loc[event.index[0], 'Model Name'])

def swap_visibility():
    return gr.update(visible=True), gr.update(visible=False), gr.update(value=''), gr.update(value=None)

def process_file_upload(file):
    return file.name, gr.update(value=file.name)

def show_hop_slider(pitch_detection_algo):
    if pitch_detection_algo == 'mangio-crepe':
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)

if __name__ == '__main__':
    parser = ArgumentParser(description='Создать AI-кавер песни в директории song_output/id.', add_help=True)
    parser.add_argument("--share", action="store_true", dest="share_enabled", default=False, help="Разрешить совместное использование")
    parser.add_argument("--listen", action="store_true", default=False, help="Сделать WebUI доступным из вашей локальной сети.")
    parser.add_argument('--listen-host', type=str, help='Имя хоста, которое будет использовать сервер.')
    parser.add_argument('--listen-port', type=int, help='Порт прослушивания, который будет использовать сервер.')
    args = parser.parse_args()

    voice_models = get_current_models(rvc_models_dir)
    with open(os.path.join(rvc_models_dir, 'public_models.json'), encoding='utf8') as infile:
        public_models = json.load(infile)

    with gr.Blocks(title='CoverGen - Politrees') as app:

        with gr.Tab("Контакты"):
                gr.Image(value=image_path)

        with gr.Tab("CoverGen"):
            with gr.Accordion('Основные настройки'):
                with gr.Row():
                    with gr.Column():
                        rvc_model = gr.Dropdown(voice_models, label='Модели голоса', info='Директория "AICoverGen --> rvc_models". После добавления новых моделей в эту директорию, нажмите кнопку "Обновить список моделей"')
                        ref_btn = gr.Button('Обновить список моделей 🔁', variant='primary')

                    with gr.Column() as yt_link_col:
                        song_input = gr.Text(label='Входная песня', info='Ссылка на песню на YouTube или полный путь к локальному файлу')
                        show_file_upload_button = gr.Button('Загрузить файл с компьютера')
    
                    with gr.Column(visible=False) as file_upload_col:
                        local_file = gr.File(label='Аудио-файл')
                        song_input_file = gr.UploadButton('Загрузить 📂', file_types=['audio'], variant='primary')
                        show_yt_link_button = gr.Button('Вставить ссылку на YouTube / Путь к файлу')
                        song_input_file.upload(process_file_upload, inputs=[song_input_file], outputs=[local_file, song_input])
    
                    with gr.Column():
                        pitch = gr.Slider(-24, 24, value=0, step=1, label='Изменение тона (только вокал)', info='Обычно используйте 1 для преобразования мужского голоса в женский и -1 для обратного преобразования. (Октавы)')
                        pitch_all = gr.Slider(-12, 12, value=0, step=1, label='Общее изменение тона', info='Изменяет тон/тональность вокала и инструментов вместе. Незначительное изменение этого параметра ухудшает качество звука. (Полутоны)')
                    show_file_upload_button.click(swap_visibility, outputs=[file_upload_col, yt_link_col, song_input, local_file])
                    show_yt_link_button.click(swap_visibility, outputs=[yt_link_col, file_upload_col, song_input, local_file])

            with gr.Accordion('Настройки преобразования голоса', open=False):
                with gr.Row():
                    index_rate = gr.Slider(0, 1, value=0.5, label='Скорость индексации', info="Управляет тем, сколько акцента AI-голоса сохранять в вокале. Выбор меньших значений может помочь снизить артефакты, присутствующие в аудио")
                    filter_radius = gr.Slider(0, 7, value=3, step=1, label='Радиус фильтра', info='Если >=3: применяет медианную фильтрацию к результатам выделения тона. Может уменьшить шум дыхания')
                    rms_mix_rate = gr.Slider(0, 1, value=0.25, label='Скорость смешивания RMS', info="Управляет тем, насколько точно воспроизводится громкость оригинального голоса (0) или фиксированная громкость (1)")
                    protect = gr.Slider(0, 0.5, value=0.33, label='Скорость защиты', info='Защищает глухие согласные и звуки дыхания. Увеличение параметра до максимального значения 0,5 обеспечивает полную защиту')
                    with gr.Column():
                        f0_method = gr.Dropdown(['rmvpe', 'mangio-crepe'], value='rmvpe', label='Метод выделения тона', info='Лучший вариант - rmvpe (чистота голоса), затем mangio-crepe (более плавный голос)')
                        crepe_hop_length = gr.Slider(32, 320, value=128, step=1, visible=False, label='Длина шага Crepe', info='Меньшие значения ведут к более длительным преобразованиям и большему риску трещин в голосе, но лучшей точности тона')
                        f0_method.change(show_hop_slider, inputs=f0_method, outputs=crepe_hop_length)
                keep_files = gr.Checkbox(label='Сохранить промежуточные файлы', info='Сохранять все аудиофайлы, созданные в директории song_output/id, например, Извлеченный Вокал/Инструментал')

            with gr.Accordion('Настройки сведения аудио', open=False):
                gr.Markdown('### Изменение громкости (децибел)')
                with gr.Row():
                    main_gain = gr.Slider(-20, 20, value=0, step=1, label='Основной вокал')
                    backup_gain = gr.Slider(-20, 20, value=0, step=1, label='Дополнительный вокал (бэки)')
                    inst_gain = gr.Slider(-20, 20, value=0, step=1, label='Музыка')

                gr.Markdown('### Управление реверберацией в AI-вокале')
                with gr.Row():
                    reverb_rm_size = gr.Slider(0, 1, value=0.15, label='Размер комнаты', info='Чем больше комната, тем дольше время реверберации')
                    reverb_wet = gr.Slider(0, 1, value=0.2, label='Уровень влажности', info='Уровень AI-вокала с реверберацией')
                    reverb_dry = gr.Slider(0, 1, value=0.8, label='Уровень сухости', info='Уровень AI-вокала без реверберации')
                    reverb_damping = gr.Slider(0, 1, value=0.7, label='Уровень демпфирования', info='Поглощение высоких частот в реверберации')

                gr.Markdown('### Формат выходного аудио')
                output_format = gr.Dropdown(['mp3', 'wav'], value='mp3', label='Тип выходного файла', info='mp3: малый размер файла, хорошее качество. wav: большой размер файла, лучшее качество')

            with gr.Row():
                generate_btn = gr.Button("Генерировать", variant='primary', scale = 2)
                ai_cover = gr.Audio(label='AI-кавер', show_share_button=False, scale = 5)
                clear_btn = gr.ClearButton(value='Сброс параметров', components=[song_input, rvc_model, keep_files, local_file], scale = 0.5)


            ref_btn.click(update_models_list, None, outputs=rvc_model)
            is_webui = gr.Number(value=1, visible=False)
            generate_btn.click(song_cover_pipeline,
                               inputs=[song_input, rvc_model, pitch, keep_files, is_webui, main_gain, backup_gain,
                                       inst_gain, index_rate, filter_radius, rms_mix_rate, f0_method, crepe_hop_length,
                                       protect, pitch_all, reverb_rm_size, reverb_wet, reverb_dry, reverb_damping,
                                       output_format],
                               outputs=[ai_cover])
            clear_btn.click(lambda: [0, 0, 0, 0, 0.5, 3, 0.25, 0.33, 'rmvpe', 128, 0, 0.15, 0.2, 0.8, 0.7, 'mp3', None],
                            outputs=[pitch, main_gain, backup_gain, inst_gain, index_rate, filter_radius, rms_mix_rate,
                                     protect, f0_method, crepe_hop_length, pitch_all, reverb_rm_size, reverb_wet,
                                     reverb_dry, reverb_damping, output_format, ai_cover])

#        with gr.Tab("Video-CoverGen"):
#            gr.Label('Это на будущее, если найду силы сделать)', show_label=False)

        with gr.Tab('Загрузка модели'):
            with gr.Tab('Загрузить по ссылке'):
                with gr.Row():
                    model_zip_link = gr.Text(label='Ссылка на загрузку модели', info='Это должна быть ссылка на zip-файл, содержащий файл модели .pth и необязательный файл .index.', scale = 3)
                    model_name = gr.Text(label='Имя модели', info='Дайте вашей загружаемой модели уникальное имя, отличное от других голосовых моделей.', scale = 1.5)

                with gr.Row():
                    dl_output_message = gr.Text(label='Сообщение вывода', interactive=False, scale=3)
                    download_btn = gr.Button('Загрузить модель', variant='primary', scale=1)

                download_btn.click(download_online_model, inputs=[model_zip_link, model_name], outputs=dl_output_message)

            with gr.Tab('Загрузить локально'):
                gr.Markdown('## Загрузка локально обученной модели RVC v2 и файла индекса')
                gr.Markdown('- Найдите файл модели (папка weights) и необязательный файл индекса (папка logs/[имя])')
                gr.Markdown('- Сжать файлы в zip-файл')
                gr.Markdown('- Загрузить zip-файл и дать уникальное имя голосу')
                gr.Markdown('- Нажмите кнопку "Загрузить модель"')
    
                with gr.Row():
                    with gr.Column(scale=2):
                        zip_file = gr.File(label='Zip-файл')

                    with gr.Column(scale=1.5):
                        local_model_name = gr.Text(label='Имя модели', info='Дайте вашей загружаемой модели уникальное имя, отличное от других голосовых моделей.')
                        model_upload_button = gr.Button('Загрузить модель', variant='primary')

                with gr.Row():
                    local_upload_output_message = gr.Text(label='Сообщение вывода', interactive=False)
                    model_upload_button.click(upload_local_model, inputs=[zip_file, local_model_name], outputs=local_upload_output_message)

    app.launch(
        share=args.share_enabled,
        enable_queue=True,
        server_name=None if not args.listen else (args.listen_host or '0.0.0.0'),
        server_port=args.listen_port,
    )
