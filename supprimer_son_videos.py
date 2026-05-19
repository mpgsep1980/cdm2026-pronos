"""
supprimer_son_videos.py
=======================
Supprime la piste audio de toutes les vidéos MP4 du dossier CDM 2026.
Requiert : pip install moviepy

Usage : python supprimer_son_videos.py
"""

from pathlib import Path
from moviepy import VideoFileClip

DOSSIER = Path(__file__).parent
videos  = sorted(DOSSIER.glob("*.mp4"))
# Exclure les fichiers déjà traités
videos  = [v for v in videos if not v.stem.endswith("_nosound")]

if not videos:
    print("Aucune vidéo MP4 à traiter.")
    exit()

print(f"{len(videos)} vidéo(s) trouvée(s)\n")

for src in videos:
    dst = src.with_stem(src.stem + "_nosound")
    print(f"  ⏳ {src.name} → {dst.name} ...")
    try:
        clip = VideoFileClip(str(src))
        clip.without_audio().write_videofile(
            str(dst),
            codec="libx264",
            audio=False,
            logger=None       # silencieux
        )
        clip.close()
        print(f"  ✅ OK")
    except Exception as e:
        print(f"  ❌ Erreur : {e}")

print("\nTerminé. Vérifiez les fichiers *_nosound.mp4,")
print("puis lancez ce script avec REMPLACER=True pour écraser les originaux.")

