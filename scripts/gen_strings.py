"""Writes strings.json and the translations: python3 scripts/gen_strings.py."""
import json, pathlib
L = "en"
def t(en, fr): return en if L == 'en' else fr
def OUT():
    entity = {
     "binary_sensor": {"connected": t("Connected","Connecté"), "undervoltage": t("Undervoltage","Sous-tension")},
     "button": {"clear": t("Give back to capture","Rendre à la capture"), "clear_all": t("Clear all sources","Effacer toutes les sources"),
       "poweroff": t("Power off","Éteindre"), "reboot": t("Restart","Redémarrer")},
     "camera": {"capture": t("Captured picture","Image capturée"), "led_colors": t("LED colors","Couleurs des LEDs")},
     "number": {
      "brightness_gain": t("Brightness","Luminosité"), "saturation_gain": t("Saturation","Saturation"), "gamma": t("Gamma","Gamma"),
      "backlight": t("Backlight threshold","Seuil de rétroéclairage"), "power_limit": t("Power limit","Limite de puissance"),
      "scale_output": t("Output scale","Échelle de sortie"), "smoothing_time": t("Smoothing time","Durée du lissage"),
      "smoothing_frequency": t("Smoothing frequency","Fréquence du lissage"), "blackborder_threshold": t("Black border threshold","Seuil des bandes noires"),
      "grabber_brightness": t("Grabber brightness","Luminosité du grabber"), "grabber_contrast": t("Grabber contrast","Contraste du grabber"),
      "grabber_saturation": t("Grabber saturation","Saturation du grabber"), "grabber_hue": t("Grabber hue","Teinte du grabber"),
      "crop_top": t("Crop top","Recadrage haut"), "crop_bottom": t("Crop bottom","Recadrage bas"), "crop_left": t("Crop left","Recadrage gauche"), "crop_right": t("Crop right","Recadrage droite"),
     },
     "select": {
      "source": {"name": t("Source","Source"), "state": {"auto": t("Automatic","Automatique")}},
      "processing": {"name": t("Processing","Traitement"), "state": {"advanced": t("Advanced","Avancé"), "multicolor_mean": t("Multicolor mean","Moyenne multicolore"), "unicolor_mean": t("Single color mean","Moyenne unicolore"), "weighted": t("Weighted","Pondéré")}},
      "color_temperature": {"name": t("Color temperature","Température de couleur"), "state": {"disabled": t("Off","Désactivée"), "cold": t("Cold","Froide"), "neutral": t("Neutral","Neutre"), "warm": t("Warm","Chaude"), "custom": t("Custom","Personnalisée")}},
      "smoothing_type": {"name": t("Smoothing type","Type de lissage"), "state": {"stepper": "Stepper", "yuvinterpolator": t("YUV interpolator","Interpolation YUV"), "rgbinterpolator": t("RGB interpolator","Interpolation RVB"), "hybridinterpolator": t("Hybrid interpolator","Interpolation hybride"), "hybridrgbinterpolator": t("Hybrid RGB interpolator","Interpolation hybride RVB"), "exponentialinterpolator": t("Exponential interpolator","Interpolation exponentielle")}},
      "blackborder_mode": {"name": t("Black border mode","Mode des bandes noires"), "state": {"default": t("Default","Par défaut"), "classic": t("Classic","Classique"), "osd": "OSD", "letterbox": "Letterbox"}},
     },
     "sensor": {
      "cpu": t("CPU","Processeur"), "cpu_temperature": t("CPU temperature","Température du processeur"), "memory": t("Memory","Mémoire"),
      "capture_fps": t("Capture rate","Fréquence de capture"), "grabber": t("Grabber","Grabber"), "video_mode": t("Video mode","Mode vidéo"),
      "version": t("Version","Version"), "output_fps": t("Output rate","Fréquence de sortie"), "led_fps": t("LED rate","Fréquence des LEDs"),
      "led_count": t("LEDs","LEDs"), "led_device": t("LED device","Appareil LED"), "average_color": t("Average color","Couleur moyenne"),
      "visible_source": {"name": t("Visible source","Source affichée"), "state": {
        "none": t("None","Aucune"), "videograbber": t("Video capture","Capture vidéo"), "systemgrabber": t("System capture","Capture système"),
        "color": t("Color","Couleur"), "effect": t("Effect","Effet"), "image": t("Image","Image"), "flatbufserver": "Flatbuffers",
        "protoserver": "Protobuf", "rawudpserver": "UDP", "cec": "CEC", "unknown": t("Other","Autre")}},
     },
     "switch": {
      "led_output": t("LED output","Sortie LED"), "video_capture": t("Video capture","Capture vidéo"), "system_capture": t("System capture","Capture système"),
      "smoothing": t("Smoothing","Lissage"), "black_border": t("Black border detection","Détection des bandes noires"), "forwarder": t("Forwarder","Transfert"),
      "hdr": t("HDR tone mapping","Tone mapping HDR"), "continuous_output": t("Continuous output","Sortie continue"),
      "anti_flickering": t("Anti-flickering filter","Filtre anti-scintillement"), "background_effect": t("Background effect","Effet d’arrière-plan"),
      "boot_effect": t("Boot effect","Effet au démarrage"), "auto_tone_mapping": t("Automatic tone mapping","Tone mapping automatique"),
      "signal_detection": t("Signal detection","Détection du signal"),
     },
    }
    def names(d):
        return {k: (v if isinstance(v, dict) else {"name": v}) for k, v in d.items()}
    out = {
     "config": {
      "flow_title": "{name}",
      "step": {
       "user": {"title": "HyperHDR", "description": t("Address of the HyperHDR server. The admin password unlocks the settings, the captured picture and the configuration; without it, HyperHDR's default password is tried.","Adresse du serveur HyperHDR. Le mot de passe admin débloque les réglages, l’image capturée et la configuration ; sans lui, le mot de passe par défaut d’HyperHDR est essayé."),
         "data": {"host": t("Host","Hôte"), "port": "Port", "password": t("Admin password","Mot de passe admin")},
         "data_description": {"host": t("IP address or name of the machine running HyperHDR","Adresse IP ou nom de la machine qui fait tourner HyperHDR"), "port": t("Web server port (8090 by default)","Port du serveur web (8090 par défaut)"), "password": t("Optional: leave empty to try HyperHDR's default","Optionnel : vide, le mot de passe par défaut d’HyperHDR est essayé")}},
       "discovery_confirm": {"title": t("HyperHDR found","HyperHDR trouvé"), "description": t("Add {name} ({host})?","Ajouter {name} ({host}) ?"), "data": {"password": t("Admin password","Mot de passe admin")}, "data_description": {"password": t("Optional: leave empty to try HyperHDR's default","Optionnel : vide, le mot de passe par défaut d’HyperHDR est essayé")}},
       "reauth_confirm": {"title": t("HyperHDR password","Mot de passe HyperHDR"), "description": t("HyperHDR at {host} refused the stored credentials (the password changed?).","HyperHDR sur {host} refuse les identifiants enregistrés (le mot de passe a changé ?)."), "data": {"password": t("Admin password","Mot de passe admin")}},
       "reconfigure": {"title": "HyperHDR", "data": {"host": t("Host","Hôte"), "port": "Port", "password": t("Admin password","Mot de passe admin")}},
      },
      "error": {
       "cannot_connect": t("Cannot connect to HyperHDR","Impossible de joindre HyperHDR"),
       "invalid_auth": t("Wrong password","Mot de passe incorrect"),
       "auth_required": t("This HyperHDR asks for authentication: enter its admin password","Ce HyperHDR demande une authentification : saisis son mot de passe admin"),
       "too_old": t("HyperHDR 21 or newer is needed","HyperHDR 21 ou plus récent est nécessaire"),
       "unknown": t("Unexpected error","Erreur inattendue"),
      },
      "abort": {
       "already_configured": t("This HyperHDR is already set up","Ce HyperHDR est déjà configuré"),
       "reauth_successful": t("Credentials updated","Identifiants mis à jour"),
       "reconfigure_successful": t("HyperHDR updated","HyperHDR mis à jour"),
       "wrong_server": t("This is another HyperHDR server","C’est un autre serveur HyperHDR"),
       "cannot_connect": t("Cannot connect to HyperHDR","Impossible de joindre HyperHDR"),
      },
     },
     "options": {"step": {"init": {"title": t("HyperHDR options","Options HyperHDR"),
       "data": {"name_prefix": t("Name prefix","Préfixe des noms"), "priority": t("Priority of Home Assistant","Priorité de Home Assistant"), "performance": t("Host health and frame rates","Santé de la machine et fréquences d’images"), "stream_fps": t("Captured picture rate","Fréquence de l’image capturée"), "led_interval": t("LED colors refresh","Rafraîchissement des couleurs des LEDs")},
       "data_description": {"name_prefix": t("For example salon-ambilight-hyperhdr: the server becomes salon-ambilight-hyperhdr-hub, each strip salon-ambilight-hyperhdr- followed by its HyperHDR name, spaces as _. Saving it renames the devices and recreates the entity ids (automations using the old ids must be updated). Empty: HyperHDR's names","Par exemple salon-ambilight-hyperhdr : le serveur devient salon-ambilight-hyperhdr-hub, chaque bandeau salon-ambilight-hyperhdr- suivi de son nom HyperHDR, espaces en _. L’enregistrer renomme les appareils et recrée les ID des entités (les automatisations qui utilisent les anciens ID sont à mettre à jour). Vide : les noms d’HyperHDR"), "priority": t("Colors and effects set from Home Assistant use it; lower wins (the capture is 240)","Les couleurs et effets lancés depuis Home Assistant l’utilisent ; plus petit = prioritaire (la capture est à 240)"), "performance": t("CPU, temperature, memory and undervoltage every 30 s; fps every minute","CPU, température, mémoire et sous-tension toutes les 30 s ; fps chaque minute"), "stream_fps": t("While the camera is viewed","Pendant qu’on regarde la caméra"), "led_interval": t("While the LED camera is viewed","Pendant qu’on regarde la caméra des LEDs")},
       "sections": {"ssh": {"name": t("Power off and restart (SSH)","Extinction et redémarrage (SSH)"),
         "description": t("To power the machine off cleanly before cutting its power. Nothing to install on it: SSH turned on (Raspberry Pi Imager, Services tab) and the user set there.","Pour éteindre la machine proprement avant de lui couper le courant. Rien à installer dessus : le SSH activé (Raspberry Pi Imager, onglet Services) et l’utilisateur choisi là."),
         "data": {"ssh_username": t("User","Utilisateur"), "ssh_password": t("Password","Mot de passe"), "ssh_port": t("SSH port","Port SSH")},
         "data_description": {"ssh_username": t("Empty: no power buttons","Vide : pas de boutons d’alimentation"), "ssh_password": t("The user's password, also given to sudo; empty keeps the saved one","Le mot de passe de l’utilisateur, donné aussi à sudo ; vide garde celui enregistré"), "ssh_port": t("22 by default","22 par défaut")}}}}},
      "error": {
       "ssh_password_required": t("Enter the SSH password","Saisis le mot de passe SSH"),
       "ssh_invalid_auth": t("SSH refused this user or password","SSH refuse cet utilisateur ou ce mot de passe"),
       "ssh_sudo": t("Logged in, but sudo refused: this user may not use sudo","Connecté, mais sudo refuse : cet utilisateur n’a pas le droit d’utiliser sudo"),
       "ssh_host_key": t("The machine's SSH key changed","La clé SSH de la machine a changé"),
       "ssh_cannot_connect": t("Cannot reach the machine over SSH (is SSH turned on?)","Impossible de joindre la machine en SSH (le SSH est-il activé ?)"),
       "unknown": t("Unexpected error","Erreur inattendue")}},
     "entity": {k: names(v) for k, v in entity.items()},
     "exceptions": {
      "ssh_invalid_auth": {"message": t("SSH refused the user or password: {error}","SSH refuse l’utilisateur ou le mot de passe : {error}")},
      "ssh_sudo": {"message": t("sudo refused: {error}","sudo a refusé : {error}")},
      "ssh_host_key": {"message": t("The machine's SSH key changed (reinstalled?): save the SSH options again. {error}","La clé SSH de la machine a changé (réinstallée ?) : enregistre de nouveau les options SSH. {error}")},
      "ssh_cannot_connect": {"message": t("Cannot reach the machine over SSH: {error}","Impossible de joindre la machine en SSH : {error}")},
      "command_failed": {"message": t("HyperHDR refused {command}: {error}","HyperHDR a refusé {command} : {error}")},
      "not_connected": {"message": t("HyperHDR is not connected: {error}","HyperHDR n’est pas connecté : {error}")},
      "unknown_source": {"message": t("Unknown source: {source}","Source inconnue : {source}")},
      "entry_not_loaded": {"message": t("This HyperHDR is not loaded","Ce HyperHDR n’est pas chargé")},
      "admin_required": {"message": t("This needs HyperHDR's admin password (reconfigure the integration)","Il faut le mot de passe admin d’HyperHDR (reconfigure l’intégration)")},
     },
     "services": {
      "set_color": {"name": t("Set color","Afficher une couleur"), "description": t("Shows a color on the LEDs, above the capture.","Affiche une couleur sur les LEDs, au-dessus de la capture."), "fields": {
         "rgb_color": {"name": t("Color","Couleur"), "description": t("Red, green, blue","Rouge, vert, bleu")},
         "priority": {"name": t("Priority","Priorité"), "description": t("Lower wins; the integration's own by default","Plus petit = prioritaire ; celle de l’intégration par défaut")},
         "duration": {"name": t("Duration","Durée"), "description": t("Milliseconds; until cleared when empty","Millisecondes ; jusqu’à effacement si vide")}}},
      "set_effect": {"name": t("Set effect","Lancer un effet"), "description": t("Runs a HyperHDR effect, above the capture.","Lance un effet HyperHDR, au-dessus de la capture."), "fields": {
         "effect": {"name": t("Effect","Effet"), "description": t("Name of the effect","Nom de l’effet")},
         "priority": {"name": t("Priority","Priorité"), "description": t("Lower wins; the integration's own by default","Plus petit = prioritaire ; celle de l’intégration par défaut")},
         "duration": {"name": t("Duration","Durée"), "description": t("Milliseconds; until cleared when empty","Millisecondes ; jusqu’à effacement si vide")}}},
      "clear": {"name": t("Clear","Effacer"), "description": t("Removes a color or an effect: the capture shows again.","Retire une couleur ou un effet : la capture réapparaît."), "fields": {
         "priority": {"name": t("Priority","Priorité"), "description": t("The integration's own by default","Celle de l’intégration par défaut")}}},
      "get_config": {"name": t("Get configuration","Lire la configuration"), "description": t("Returns the whole HyperHDR configuration of an instance (admin).","Renvoie toute la configuration HyperHDR d’une instance (admin)."), "fields": {
         "config_entry_id": {"name": "HyperHDR", "description": t("The HyperHDR server","Le serveur HyperHDR")},
         "instance": {"name": "Instance", "description": t("0 for the first","0 pour la première")}}},
      "set_config": {"name": t("Set configuration","Modifier la configuration"), "description": t("Writes HyperHDR settings; a section may be partial, HyperHDR merges it (admin).","Écrit des réglages HyperHDR ; une section peut être partielle, HyperHDR la fusionne (admin)."), "fields": {
         "config_entry_id": {"name": "HyperHDR", "description": t("The HyperHDR server","Le serveur HyperHDR")},
         "instance": {"name": "Instance", "description": t("0 for the first","0 pour la première")},
         "config": {"name": t("Configuration","Configuration"), "description": t("Sections and values, as in get_config","Sections et valeurs, comme dans get_config")}}},
      "backup": {"name": t("Backup","Sauvegarde"), "description": t("Returns HyperHDR's full backup (admin).","Renvoie la sauvegarde complète d’HyperHDR (admin)."), "fields": {
         "config_entry_id": {"name": "HyperHDR", "description": t("The HyperHDR server","Le serveur HyperHDR")}}},
     },
    }
    return out


def build(language):
    global L
    L = language
    return OUT()

root = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "ha_hyperhdr"
for language, path in (("en", root / "strings.json"), ("en", root / "translations" / "en.json"), ("fr", root / "translations" / "fr.json")):
    path.write_text(json.dumps(build(language), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
