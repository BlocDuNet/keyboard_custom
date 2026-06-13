@echo off
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
:: Remplacez l'URL ci-dessous par l'URL de votre dépôt si nécessaire
SET "REPO_URL=https://github.com/votre-utilisateur/keyboard_custom"
SET "BRANCH=keyboard-custom-logiciel-5579749975229344282"
:: ---------------------

echo [UPDATE] Verification de Git...
where git >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Git est installe.
    if exist .git (
        echo [UPDATE] Mise a jour via git pull...
        git pull origin %BRANCH%
    ) else (
        echo [UPDATE] Initialisation du depot git...
        git init
        git remote add origin %REPO_URL%
        git fetch
        git checkout %BRANCH%
    )
) else (
    echo [INFO] Git n'est pas installe. Utilisation de PowerShell pour le telechargement...

    SET "ZIP_URL=%REPO_URL%/archive/refs/heads/%BRANCH%.zip"
    echo [UPDATE] Telechargement de : !ZIP_URL!

    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $url = '%REPO_URL%/archive/refs/heads/%BRANCH%.zip'; Invoke-WebRequest -Uri $url -OutFile 'update.zip'"

    if exist update.zip (
        echo [UPDATE] Extraction des fichiers...
        powershell -Command "Expand-Archive -Path 'update.zip' -DestinationPath 'temp_update' -Force"

        echo [UPDATE] Deplacement des fichiers...
        xcopy /s /y "temp_update\*" "."

        echo [UPDATE] Nettoyage...
        rd /s /q "temp_update"
        del "update.zip"
        echo [OK] Mise a jour terminee.
    ) else (
        echo [ERREUR] Impossible de telecharger la mise a jour. Verifiez l'URL ou votre connexion.
    )
)

pause
