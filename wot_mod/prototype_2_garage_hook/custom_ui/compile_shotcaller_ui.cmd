@echo off
setlocal
set "PLAYERGLOBAL_HOME=D:\antigravity\shot-caller\.tools\flash\playerglobal"
set "JAVA_HOME=D:\antigravity\shot-caller\.tools\flash\jre\jdk-17.0.19+10-jre"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "FLEX_HOME=D:\antigravity\shot-caller\.tools\flash\apache-flex-sdk-4.16.1"
set "SOURCE_ROOT=D:\antigravity\shot-caller\wot_mod\prototype_2_garage_hook\custom_ui\src"
set "OUTPUT_DIR=D:\antigravity\shot-caller\wot_mod\prototype_2_garage_hook\custom_ui\dist"
set "WG_ABSTRACT_VIEW_SWC=D:\antigravity\shot-caller\wot_mod\prototype_2_garage_hook\custom_ui\wg_contract_stub\wot_abstract_view_contract.swc"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
echo "%JAVA_HOME%\bin\java.exe" -Xmx1536m -Dsun.io.useCanonCaches=false -Djava.util.Arrays.useLegacyMergeSort=true -jar "%FLEX_HOME%\lib\mxmlc.jar" +flexlib="%FLEX_HOME%\frameworks" -compiler.source-path+="%SOURCE_ROOT%" -external-library-path+="%WG_ABSTRACT_VIEW_SWC%" -target-player=27.0 -output="%OUTPUT_DIR%\shotcallerVehicleWindow.swf" "%SOURCE_ROOT%\shotcaller\ui\ShotcallerVehicleWindow.as"
"%JAVA_HOME%\bin\java.exe" -Xmx1536m -Dsun.io.useCanonCaches=false -Djava.util.Arrays.useLegacyMergeSort=true -jar "%FLEX_HOME%\lib\mxmlc.jar" +flexlib="%FLEX_HOME%\frameworks" -compiler.source-path+="%SOURCE_ROOT%" -external-library-path+="%WG_ABSTRACT_VIEW_SWC%" -target-player=27.0 -output="%OUTPUT_DIR%\shotcallerVehicleWindow.swf" "%SOURCE_ROOT%\shotcaller\ui\ShotcallerVehicleWindow.as"
if errorlevel 1 exit /b %ERRORLEVEL%
echo "%JAVA_HOME%\bin\java.exe" -Xmx1536m -Dsun.io.useCanonCaches=false -Djava.util.Arrays.useLegacyMergeSort=true -jar "%FLEX_HOME%\lib\mxmlc.jar" +flexlib="%FLEX_HOME%\frameworks" -compiler.source-path+="%SOURCE_ROOT%" -external-library-path+="%WG_ABSTRACT_VIEW_SWC%" -target-player=27.0 -output="%OUTPUT_DIR%\shotcallerVehicleFilters.swf" "%SOURCE_ROOT%\shotcaller\ui\ShotcallerVehicleFilters.as"
"%JAVA_HOME%\bin\java.exe" -Xmx1536m -Dsun.io.useCanonCaches=false -Djava.util.Arrays.useLegacyMergeSort=true -jar "%FLEX_HOME%\lib\mxmlc.jar" +flexlib="%FLEX_HOME%\frameworks" -compiler.source-path+="%SOURCE_ROOT%" -external-library-path+="%WG_ABSTRACT_VIEW_SWC%" -target-player=27.0 -output="%OUTPUT_DIR%\shotcallerVehicleFilters.swf" "%SOURCE_ROOT%\shotcaller\ui\ShotcallerVehicleFilters.as"
echo Exit code: %ERRORLEVEL%
exit /b %ERRORLEVEL%
