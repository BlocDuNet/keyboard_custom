# Keyboard Custom - Logiciel de personnalisation de claviers

Ce projet permet de distinguer plusieurs claviers (même identiques) sous Windows et de leur attribuer des fonctions différentes.

## Contenu du projet

- `kb_list.py` : Liste tous les claviers connectés avec leurs identifiants Windows.
- `kb_monitor.py` : Affiche en temps réel les touches pressées et le clavier d'origine.
- `kb_correlator.py` : Démonstration technique de la corrélation entre l'ID du clavier et l'interception de touche.
- `sayo_hid.py` : Module de base pour communiquer avec les claviers Sayodevice (RGB, etc.) via HID.
- `main_app.py` : **Application principale**. Lancez-la, appuyez sur une touche pour identifier le clavier cible, et la touche 'A' de ce clavier sera automatiquement transformée en 'B'.

## Installation

1. Assurez-vous d'avoir Python installé sur Windows.
2. Installez la bibliothèque HID pour le support Sayodevice :
   ```bash
   pip install hidapi
   ```
3. (Optionnel) Pour les fonctions avancées de l'interface Windows, `pywin32` peut être utile, mais le code actuel utilise `ctypes` pour éviter les dépendances lourdes.

## Utilisation de l'application principale

Lancez `main_app.py` avec des droits d'administrateur (nécessaire pour intercepter les touches système) :

```bash
python main_app.py
```

1. Le logiciel attendra que vous appuyiez sur une touche.
2. Le clavier que vous avez utilisé sera "marqué" comme cible.
3. Désormais, sur ce clavier spécifique, la touche 'A' enverra un 'B'. Les autres claviers ne seront pas affectés.

## Évolutions pour le RGB (Sayodevice)

Le fichier `sayo_hid.py` contient la structure pour envoyer des rapports HID. Pour modifier le RGB, vous devrez identifier les octets spécifiques acceptés par votre modèle Sayodevice. Le Vendor ID utilisé est `0x8089`.
