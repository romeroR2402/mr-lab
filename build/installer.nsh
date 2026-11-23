; Pasos adicionales del instalador de Mobile Recovery Lab.
; Registra los controladores USB integrados para que la estación no dependa de
; instalaciones externas. Se usa Sysnative para invocar el pnputil de 64 bits.

!macro customInstall
  IfFileExists "$INSTDIR\resources\drivers\android-usb\android_winusb.inf" 0 mrlab_no_android_driver
    DetailPrint "Registrando controlador USB Android..."
    nsExec::ExecToLog '"$WINDIR\Sysnative\pnputil.exe" /add-driver "$INSTDIR\resources\drivers\android-usb\android_winusb.inf" /install'
    Pop $0
    DetailPrint "pnputil terminó con código $0"
  mrlab_no_android_driver:
!macroend
