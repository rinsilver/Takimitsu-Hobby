@echo off
title Takimitsu Hobby
color 0A

echo ===================================================
echo    DANG KIEM TRA VA CAI DAT THU VIEN TU DONG...
echo ===================================================
pip install -r requirements.txt

echo.
echo ===================================================
echo       KHOI DONG SERVER TAKIMITSU HOBBY...
echo ===================================================
python app.py

pause