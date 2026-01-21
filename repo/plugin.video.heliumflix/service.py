import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import json
import time

ADDON = xbmcaddon.Addon()
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
PROGRESS_FILE = os.path.join(PROFILE_PATH, 'progress.json')

class HeliumMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.player = HeliumPlayer()
        # Loop para manter o script vivo
        while not self.abortRequested():
            if self.waitForAbort(1):
                break

class HeliumPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.tracking_id = ""

    def onAVStarted(self):
        # SEGRED0: Pega o ID que enviamos pelo default.py
        self.tracking_id = xbmcgui.Window(10000).getProperty('helium_playing_url')

    def onPlayBackStopped(self):
        self.save_progress()

    def onPlayBackEnded(self):
        self.save_progress(finished=True)

    def save_progress(self, finished=False):
        if not self.tracking_id:
            return

        # Pega tempos (com proteção contra valores nulos)
        try:
            time.sleep(1) # Espera o player estabilizar
            curr_time = self.getTime()
            total_time = self.getTotalTime()
        except:
            return

        if total_time > 0:
            # Carrega banco de dados
            data = {}
            if os.path.exists(PROGRESS_FILE):
                try:
                    with open(PROGRESS_FILE, 'r') as f: data = json.load(f)
                except: pass

            # Calcula se viu tudo
            watched = 1 if finished or (curr_time / total_time) > 0.9 else 0
            
            # Se já foi visto, não desmarca. Se não, atualiza o tempo.
            old_watched = data.get(self.tracking_id, {}).get('watched', 0)
            final_watched = 1 if old_watched == 1 else watched

            data[self.tracking_id] = {
                "time": curr_time if final_watched == 0 else 0,
                "total": total_time,
                "watched": final_watched
            }

            # Salva
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(data, f)
            
            # Limpa a variável
            xbmcgui.Window(10000).clearProperty('helium_playing_url')

if __name__ == '__main__':
    HeliumMonitor()