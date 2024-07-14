import edge_tts
import os
import shutil
import librosa
import numpy as np
import soundfile as sf
import gc
import hashlib
import subprocess
from rvc import Config, load_hubert, get_vc, rvc_infer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rvc_models_dir = os.path.join(BASE_DIR, 'rvc_models')
output_dir = os.path.join(BASE_DIR, 'song_output')

def get_rvc_model(voice_model):
    model_dir = os.path.join(rvc_models_dir, voice_model)
    rvc_model_path = next((os.path.join(model_dir, f) for f in os.listdir(model_dir) if f.endswith('.pth')), None)
    rvc_index_path = next((os.path.join(model_dir, f) for f in os.listdir(model_dir) if f.endswith('.index')), None)

    if rvc_model_path is None:
        error_msg = f'В каталоге {model_dir} отсутствует файл модели.'
        raise Exception(error_msg)

    return rvc_model_path, rvc_index_path

def convert_to_stereo(audio_path):
    wave, sr = librosa.load(audio_path, mono=False, sr=44100)
    if type(wave[0]) != np.ndarray:
        stereo_path = f'Voice_stereo.wav'
        command = shlex.split(f'ffmpeg -y -loglevel error -i "{audio_path}" -ac 2 -f wav "{stereo_path}"')
        subprocess.run(command)
        return stereo_path
    else:
        return audio_path

def get_hash(filepath):
    with open(filepath, 'rb') as f:
        file_hash = hashlib.blake2b()
        while chunk := f.read(8192):
            file_hash.update(chunk)

    return file_hash.hexdigest()[:11]

def text_to_speech(text, lang, filename):
    communicate = edge_tts.Communicate(text, lang)
    communicate.save(filename)

def voice_change(voice_model, vocals_path, output_path, pitch_change, f0_method, index_rate, filter_radius, rms_mix_rate, protect, crepe_hop_length):
    rvc_model_path, rvc_index_path = get_rvc_model(voice_model)
    device = 'cuda:0'
    config = Config(device, True)
    hubert_model = load_hubert(device, config.is_half, os.path.join(rvc_models_dir, 'hubert_base.pt'))
    cpt, version, net_g, tgt_sr, vc = get_vc(device, config.is_half, config, rvc_model_path)

    rvc_infer(rvc_index_path, index_rate, vocals_path, output_path, pitch_change, f0_method, cpt, version, net_g,
              filter_radius, tgt_sr, rms_mix_rate, protect, crepe_hop_length, vc, hubert_model)
    del hubert_model, cpt
    gc.collect()

def song_cover_pipeline(text, voice_model, pitch_change, lang='ru-RU', index_rate=0.5, filter_radius=3, rms_mix_rate=0.25, f0_method='rmvpe',
                        crepe_hop_length=128, protect=0.33, output_format='mp3'):

    if not text or not voice_model:
        raise Exception('Убедитесь, что поля модели голоса и текста заполнены.')

    song_dir = output_dir
    os.makedirs(song_dir, exist_ok=True)

    text_path = os.path.join(song_dir, 'text.wav')
    text_to_speech(text, lang, text_path)

    ai_cover_path = os.path.join(song_dir, f'Converted_Voice.{output_format}')

    if os.path.exists(ai_cover_path):
        os.remove(ai_cover_path)

    voice_change(voice_model, text_path, ai_cover_path, pitch_change, f0_method, index_rate,
                 filter_radius, rms_mix_rate, protect, crepe_hop_length)

    return ai_cover_path