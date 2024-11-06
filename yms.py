#!/usr/bin/python3

import logging
from argparse import ArgumentParser
from sys import exit

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError
from colorlog import ColoredFormatter


# Настройка логгирования
console_handler = logging.StreamHandler()
formatter = ColoredFormatter(
    "%(log_color)s%(name)s::> %(message)s",
    datefmt=None,
    reset=True,
    log_colors={
        'DEBUG': 'blue',
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
)
console_handler.setFormatter(formatter)

logger = logging.getLogger("YMS")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)


# Парсинг аргументов
parser = ArgumentParser("Yandex music sort", "python3 yms.py <token>")
parser.add_argument("token", type=str,
                    help="Allows to work with user's account")
parser.add_argument("-p", "--prefix",
                    type=str, default="(YMS) - ",
                    help="Prefix adds before playlist's name")
parser.add_argument("-u", "--unknown",
                    type=str, default="Неизвестные исполнители",
                    help="Title for playlist with unknowns artists")
parser.add_argument("-v", "--visibility",
                    type=str, default="public",
                    help="Sets visibility for new playlists. 'public' default")
parser.add_argument("--delete",
                    type=str, default="",
                    help="Deletes all playlists with specific prefix")
args = parser.parse_args()

# Создание клиента Yandex Music
client = Client(token=args.token).init()


# Чисто ради прикола буду вести подсчёт
success = 0
failed = 0


# Это ужасно
if not args.delete:
    # Получение списка всех треков
    try:
        tracklist = client.users_likes_tracks()
    except YandexMusicError as yme:
        logger.error("Не удалось получить список понравившихся треков")
        exit(1)

    try:
        tracklist = {track.title: track for track in tracklist.fetch_tracks()}
    except YandexMusicError as yme:
        logger.error("Не удалось получить полные версии понравившихся треков")
        exit(2)


    # Получение всех плейлистов
    try:
        playlists = {playlist.title: playlist for playlist in client.users_playlists_list()}
    except YandexMusicError as yme:
        logger.error("Не удалось получить список плейлистов")
        exit(3)


    # Распределение треков по плейлистам
    for track in tracklist.values():
        # Будет учитываться только первый исполнитель, остальные игнорируются
        # Если имя исполнителя равно None (судя по аннотации это возможно),
        # трек будет добавлен в плейлист с неизвестными исполнителями
        artist = track.artists[0].name if track.artists[0].name else args.unknown
        playlist_title = args.prefix + artist

        if playlist_title in playlists:
            # Получение треков в плейлисте
            playlist = playlists[playlist_title]
            
            try:
                playlist_tracks = {}
                playlist_track_shorts = playlist.fetch_tracks()

                for track_short in playlist_track_shorts:
                    playlist_track = track_short.fetch_track()
                    playlist_tracks[playlist_track.title] = playlist_track

            except YandexMusicError as yme:
                # В случае ошибки мы пропускаем трек
                failed += 1
                logger.warning(f"Не удалось получить треки из плейлиста '{playlist_title}'. "
                            f"Трек '{artist} - {track.title}' не будет добавлен")
                continue

            if track.title not in playlist_tracks:
                try:
                    updated_playlist = playlist.insert_track(track.id, track.albums[0].id)
                except YandexMusicError as yme:
                    failed += 1
                    logger.warning(f"Не удалось добавить трек '{artist} - {track.title}' в '{playlist_title}'.")
                    
                # Не знаю зачем, но на всякий случай обновлю
                playlists[playlist.title] = updated_playlist
            else:
                failed += 1
                logger.info(f"Трек '{artist} - {track.title}' пропущен")
                continue
        else:
            # Если подходящий плейлист не был найден
            try:
                playlist = client.users_playlists_create(playlist_title, args.visibility)
            except YandexMusicError as yme:
                failed += 1
                logger.warning(f"Не удалось создать плейлист '{playlist_title}'."
                            f"Трек '{artist} - {track.title}' не будет добавлен")
            
            # Это копипаст с предыдущей ветки (это плохо)
            try:
                updated_playlist = playlist.insert_track(track.id, track.albums[0].id)
            except YandexMusicError as yme:
                failed += 1
                logger.warning(f"Не удалось добавить трек '{artist} - {track.title}' в '{playlist_title}'.")

            playlists[playlist.title] = updated_playlist
        
        success += 1
        logger.info(f"Трек '{artist} - {track.title}' добавлен в '{playlist_title}'")
else:
    # Удаляем)
    # Получение всех плейлистов
    try:
        playlists = {playlist.title: playlist for playlist in client.users_playlists_list()}
    except YandexMusicError as yme:
        logger.error("Не удалось получить список плейлистов")
        exit(3)

    for playlist_title, playlist in playlists.items():
        if playlist_title.startswith(args.delete):
            try:
                if client.users_playlists_delete(playlist.kind):
                    success += 1
                    logger.info(f"Плейлист '{playlist_title}' удалён")
                else:
                    failed += 1
                    logger.warning(f"Не удалось удалить плейлист '{playlist_title}'")
            except YandexMusicError as yme:
                failed += 1
                logger.warning(f"Не удалось удалить плейлист '{playlist_title}'")
        else:
            logger.info(f"Плейлист '{playlist_title}' пропущен")

# Завершение работы
logger.info("Завершение работы скрипта.")
logger.info(f"Выполнено: {success}")
logger.info(f"Провалено: {failed}")
logger.info(f"Всего:     {success + failed}")