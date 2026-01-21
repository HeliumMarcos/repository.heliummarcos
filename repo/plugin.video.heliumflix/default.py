import sys
import json
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import os

# --- CONFIGURAÇÕES ---
ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
URL_FILMES = "https://heliummarcos.com.br/addons/filmes.json"
URL_SERIES = "https://heliummarcos.com.br/addons/series.json"

PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# --- CACHE INTELIGENTE ---
def get_json(url):
    filename = "cache_movies.json" if "filmes" in url else "cache_series.json"
    cache_file = os.path.join(PROFILE_PATH, filename)
    date_file = cache_file + ".date"
    
    if not xbmcvfs.exists(PROFILE_PATH): xbmcvfs.mkdirs(PROFILE_PATH)

    last_mod_saved = ""
    if os.path.exists(date_file):
        try:
            with open(date_file, "r") as f: last_mod_saved = f.read().strip()
        except: pass

    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Kodi-Helium/1.0')
        if last_mod_saved:
            req.add_header('If-Modified-Since', last_mod_saved)

        with urllib.request.urlopen(req, timeout=10) as response:
            data_raw = response.read().decode('utf-8')
            data = json.loads(data_raw)
            with open(cache_file, "w", encoding='utf-8') as f: json.dump(data, f)
            new_mod = response.headers.get('Last-Modified', '')
            if new_mod:
                with open(date_file, "w") as f: f.write(new_mod)
            return data
    except urllib.error.HTTPError as e:
        if e.code == 304 and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f: return json.load(f)
            except: pass
        return []
    except:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f: return json.load(f)
            except: pass
        return []

# --- INTEGRAÇÃO NATIVA (MYVIDEOS DB) ---
def get_kodi_resume(file_path):
    try:
        query = {
            "jsonrpc": "2.0",
            "method": "Files.GetFileDetails",
            "params": {"file": file_path, "media": "video", "properties": ["resume", "playcount"]},
            "id": 1
        }
        json_query = json.dumps(query)
        response = xbmc.executeJSONRPC(json_query)
        result = json.loads(response)
        
        if 'result' in result and 'filedetails' in result['result']:
            details = result['result']['filedetails']
            resume = details.get('resume', {})
            return resume.get('position', 0), resume.get('total', 0), details.get('playcount', 0)
    except:
        pass
    return 0, 0, 0

# --- LISTAGEM DE FILMES ---
def list_movies():
    xbmcplugin.setContent(ADDON_HANDLE, 'movies')
    movies = get_json(URL_FILMES)
    
    for movie in movies:
        video_url = movie.get('url')
        resume_time, total_time, playcount = get_kodi_resume(video_url)
        
        li = xbmcgui.ListItem(label=movie.get('title'))
        
        infos = {
            'mediatype': 'movie',
            'title': movie.get('title'),
            'plot': movie.get('plot'),
            'genre': movie.get('genre', ''),
            'duration': int(movie.get('duration', 0)) * 60,
            'year': int(movie.get('year', 0)),
            'mpaa': movie.get('certification'),
            'playcount': playcount,
            'overlay': xbmcgui.ICON_OVERLAY_WATCHED if playcount > 0 else xbmcgui.ICON_OVERLAY_NONE
        }
        li.setInfo('video', infos)
        
        if resume_time > 0 and playcount == 0 and total_time > 0:
            percent = (resume_time / total_time) * 100
            li.setProperty('ResumeTime', str(resume_time))
            li.setProperty('TotalTime', str(total_time))
            li.setProperty('PercentPlayed', str(int(percent)))
            li.setProperty('IsResumable', 'true')

        tech = movie.get('tech', {})
        res = int(tech.get('res', 1080))
        channels = int(tech.get('channels', 2))
        li.addStreamInfo('video', {'codec': 'h265', 'width': 3840 if res == 2160 else 1920, 'height': res})
        li.addStreamInfo('audio', {'codec': 'ac3' if channels > 2 else 'aac', 'channels': channels})
        
        li.setArt({
            'poster': movie.get('poster'), 'fanart': movie.get('fanart'),
            'clearlogo': movie.get('clearlogo') or movie.get('logo')
        })

        li.setProperty('IsPlayable', 'true')
        # Codifica a URL para passar seguramente como parametro
        url = f"{sys.argv[0]}?mode=play&url={urllib.parse.quote_plus(video_url)}"
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=False)
        
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

# --- LISTAGEM DE SÉRIES ---
def list_series():
    xbmcplugin.setContent(ADDON_HANDLE, 'tvshows')
    series = get_json(URL_SERIES)
    
    for idx, s in enumerate(series):
        li = xbmcgui.ListItem(label=s.get('title'))
        
        infos = {
            'mediatype': 'tvshow',
            'title': s.get('title'),
            'plot': s.get('plot'),
            'genre': s.get('genre', ''),
            'year': int(s.get('year', 0)),
            'mpaa': s.get('certification'),
            'status': s.get('status', '')
        }
        li.setInfo('video', infos)
        
        li.setArt({
            'poster': s.get('poster'), 'fanart': s.get('fanart'),
            'clearlogo': s.get('clearlogo') or s.get('logo')
        })
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=f"{sys.argv[0]}?mode=seasons&s_idx={idx}", listitem=li, isFolder=True)
        
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

# --- LISTAGEM DE TEMPORADAS ---
def list_seasons(s_idx):
    series = get_json(URL_SERIES)
    serie = series[int(s_idx)]
    xbmcplugin.setContent(ADDON_HANDLE, 'seasons')
    seasons = serie.get('seasons', {})
    
    for num in sorted(seasons.keys(), key=int):
        meta = seasons[num].get('metadata', {})
        label = meta.get('name', f"Temporada {num}")
        
        li = xbmcgui.ListItem(label=label)
        infos = {
            'mediatype': 'season',
            'season': int(num),
            'tvshowtitle': serie.get('title'),
            'plot': meta.get('plot', serie.get('plot')),
            'genre': serie.get('genre', '')
        }
        li.setInfo('video', infos)
        
        li.setArt({
            'poster': meta.get('poster', serie.get('poster')),
            'fanart': serie.get('fanart'),
            'clearlogo': serie.get('clearlogo') or serie.get('logo')
        })
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=f"{sys.argv[0]}?mode=episodes&s_idx={s_idx}&season={num}", listitem=li, isFolder=True)
        
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

# --- LISTAGEM DE EPISÓDIOS ---
def list_episodes(s_idx, season_num):
    series = get_json(URL_SERIES)
    serie = series[int(s_idx)]
    xbmcplugin.setContent(ADDON_HANDLE, 'episodes')
    episodes = serie.get('seasons', {}).get(season_num, {}).get('episodes', [])
    parent_genre = serie.get('genre', '')

    for ep in episodes:
        video_url = ep.get('url')
        resume_time, total_time, playcount = get_kodi_resume(video_url)
        
        li = xbmcgui.ListItem(label=ep.get('title'))
        
        infos = {
            'mediatype': 'episode',
            'title': ep.get('title'),
            'tvshowtitle': serie.get('title'),
            'plot': ep.get('plot'),
            'season': int(ep.get('season', 1)),
            'episode': int(ep.get('episode', 0)),
            'genre': parent_genre, 
            'duration': int(ep.get('duration', 0)) * 60,
            'mpaa': serie.get('certification'),
            'playcount': playcount,
            'overlay': xbmcgui.ICON_OVERLAY_WATCHED if playcount > 0 else xbmcgui.ICON_OVERLAY_NONE
        }
        li.setInfo('video', infos)
        
        if resume_time > 0 and playcount == 0 and total_time > 0:
            percent = (resume_time / total_time) * 100
            li.setProperty('ResumeTime', str(resume_time))
            li.setProperty('TotalTime', str(total_time))
            li.setProperty('PercentPlayed', str(int(percent)))
            li.setProperty('IsResumable', 'true')

        tech = ep.get('tech', {})
        res = int(tech.get('res', 1080))
        channels = int(tech.get('channels', 2))
        li.addStreamInfo('video', {'codec': 'h265', 'width': 3840 if res == 2160 else 1920, 'height': res})
        li.addStreamInfo('audio', {'codec': 'ac3', 'channels': channels})

        li.setArt({
            'thumb': ep.get('still'), 'poster': serie.get('poster'),
            'fanart': serie.get('fanart'), 'clearlogo': serie.get('clearlogo') or serie.get('logo')
        })
        
        li.setProperty('IsPlayable', 'true')
        # Codifica a URL com quote_plus para evitar quebras nos parametros
        url = f"{sys.argv[0]}?mode=play&url={urllib.parse.quote_plus(video_url)}"
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(ADDON_HANDLE)

# --- PLAYER (CORRIGIDO PARA SÉRIES COM ACENTOS/ESPAÇOS) ---
def play_video(strm_url):
    # 1. Tratamento da URL para Download
    # O link vem "sujo" (ex: .../Séries/...)
    # Precisamos garantir que está limpo primeiro (unquote) e depois codificar certo (quote)
    # safe=":/" garante que https:// não seja estragado
    try:
        url_limpa = urllib.parse.unquote(strm_url)
        url_codificada = urllib.parse.quote(url_limpa, safe=":/")
    except:
        # Fallback simples se der erro
        url_codificada = strm_url.replace(" ", "%20")

    # Define a URL final como a própria codificada (caso não consiga ler dentro)
    real_url = url_codificada
    
    try:
        # Tenta baixar o arquivo .strm para ler o conteúdo
        req = urllib.request.Request(url_codificada, headers={'User-Agent': 'Kodi-Helium/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
            
            # Se encontrou o link plugin:// dentro do arquivo, ESSA é a URL real
            if content.startswith('plugin://') or content.startswith('http'):
                real_url = content
                xbmc.log(f"[Helium] .strm lido com sucesso. Tocando: {real_url}", xbmc.LOGINFO)
            else:
                 xbmc.log(f"[Helium] .strm lido mas conteúdo inválido: {content}", xbmc.LOGWARNING)
                 
    except Exception as e:
        xbmc.log(f"[Helium] Erro ao ler .strm: {e}. Tentando tocar direto: {url_codificada}", xbmc.LOGERROR)

    # Envia para o Player do Kodi
    li = xbmcgui.ListItem(path=real_url)
    li.setInfo('video', {'dbid': 0}) 
    xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, listitem=li)

# --- ROTEADOR ---
if __name__ == '__main__':
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    mode = params.get('mode')

    if not mode:
        li = xbmcgui.ListItem(label='[B]FILMES[/B]'); li.setArt({'icon':'DefaultVideoPlaylists.png'})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, sys.argv[0]+"?mode=movies", li, True)
        li = xbmcgui.ListItem(label='[B]SÉRIES[/B]'); li.setArt({'icon':'DefaultTvShows.png'})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, sys.argv[0]+"?mode=series", li, True)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
    elif mode == 'movies': list_movies()
    elif mode == 'series': list_series()
    elif mode == 'seasons': list_seasons(params.get('s_idx'))
    elif mode == 'episodes': list_episodes(params.get('s_idx'), params.get('season'))
    elif mode == 'play': play_video(params.get('url'))