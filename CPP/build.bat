@echo off
setlocal enabledelayedexpansion

:: 设置编译器和构建类型
set BUILD_TYPE=Release
set GENERATOR="Visual Studio 17 2022"
set ARCH=x64

:: 创建build目录
if not exist build mkdir build
cd build

:: 配置CMake项目
echo Configuring CMake project...
cmake -G %GENERATOR% -A %ARCH% -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ..

:: 编译项目
echo Building project...
cmake --build . --config %BUILD_TYPE%

:: 检查编译结果
if %ERRORLEVEL% EQU 0 (
    echo Build success!
    echo Output files located in: %CD%\bin\%BUILD_TYPE%
) else (
    echo Build failed, error code: %ERRORLEVEL%
)

:: 返回原目录
cd ..

pause 