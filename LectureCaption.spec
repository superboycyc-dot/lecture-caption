from pathlib import Path
import sysconfig
import tomllib
project = Path(SPECPATH).resolve()
source = project
version = tomllib.loads((source/'pyproject.toml').read_text())['project']['version']
site = sysconfig.get_paths()['purelib']
a = Analysis([str(source/'caption.py')], pathex=[str(source),site],
    binaries=[(str(source/'native/bin/Permissions.dylib'),'native/bin'),(str(source/'native/bin/GroqSetup'),'native/bin'),(str(source/'native/bin/Keychain'),'native/bin'),(str(source/'native/bin/SystemAudio'),'native/bin'),(str(source/'native/bin/LocalSpeech'),'native/bin'),(str(source/'native/bin/LocalTranslate'),'native/bin')],
    datas=[(str(source/'vendor'),'vendor'),(str(source/'docs'),'docs'),(str(source/'LICENSE'),'.'),(str(source/'licenses'),'licenses'),(str(source/'THIRD_PARTY_NOTICES.md'),'.'),(str(source/'config.example.json'),'.'),(str(source/'assets/AppIcon.png'),'assets'),(str(source/'assets/icons'),'assets/icons')],
    hiddenimports=['wave','_sounddevice_data','scipy.signal','numpy'],
    excludes=['tkinter','matplotlib','pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='Lecture Caption',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    argv_emulation=False,target_arch='arm64',codesign_identity=None,entitlements_file=None)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='Lecture Caption')
app = BUNDLE(coll,name='Lecture Caption.app',icon=str(project/'assets/AppIcon.icns'),bundle_identifier='local.lecturecaption.desktop',
    info_plist={'CFBundleDisplayName':'Lecture Caption','CFBundleShortVersionString':version,'CFBundleVersion':'240',
    'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0',
    'NSMicrophoneUsageDescription':'收听课堂声音，用于双语字幕和课堂笔记。根据所选模式在本机识别或发送至你配置的 API。',
    'NSSpeechRecognitionUsageDescription':'使用 Apple 本地英语语音识别生成课堂字幕；音频不上传。',
    'NSAudioCaptureUsageDescription':'收听电脑播放的会议与视频音频，用于字幕和笔记。',
    'NSScreenCaptureUsageDescription':'通过系统音频采集接口收听会议和视频，不保存屏幕画面。'})
