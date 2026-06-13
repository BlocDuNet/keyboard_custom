@echo off
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
SET "REPO_URL=https://github.com/BlocDuNet/keyboard_custom.git"
SET "BRANCH=keyboard-custom-logiciel-5579749975229344282"
:: ---------------------

echo [UPDATE] Vérification de Git...
where git >nul 2>nul

if %ERRORLEVEL% equ 0 (
    echo [OK] Git est installé.

    if exist .git (
        echo [UPDATE] Mise à jour forcée depuis le dépôt...
        git remote set-url origin %REPO_URL%
        git fetch origin %BRANCH%
        git reset --hard origin/%BRANCH%
    ) else (
        echo [UPDATE] Initialisation du dépôt git...
        git init
        git remote add origin %REPO_URL%
        git fetch origin %BRANCH%
        git checkout -b %BRANCH% origin/%BRANCH%
    )

) else (
    echo [INFO] Git n'est pas installé. Téléchargement via PowerShell...

    SET "ZIP_URL=https://github.com/BlocDuNet/keyboard_custom/archive/refs/heads/%BRANCH%.zip"
    echo [UPDATE] Téléchargement de : !ZIP_URL!

    powershell -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile 'update.zip'"

    if exist update.zip (
        echo [UPDATE] Extraction des fichiers...
        powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath 'temp_update' -Force"

        echo [UPDATE] Déplacement des fichiers...
        xcopy /s /y "temp_update\*" "."

        echo [UPDATE] Nettoyage...
        rd /s /q "temp_update"
        del "update.zip"

        echo [OK] Mise à jour terminée.
    ) else (
        echo [ERREUR] Impossible de télécharger la mise à jour. Vérifiez l'URL ou votre connexion.
    )
)

pause
