cmake_minimum_required(VERSION 3.10)
project(LightmapPacker VERSION 1.0.0 LANGUAGES CXX)

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 设置默认构建类型为Release
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# 设置输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Windows特定设置
if(WIN32)
    # 添加预处理器定义
    add_definitions(-DLIGHTMAP_PACKER_EXPORTS)
    
    # 设置模块定义文件路径
    set(DEF_FILE ${CMAKE_CURRENT_SOURCE_DIR}/LightmapPacker.def)
endif()

# 源文件
set(SOURCES
    LightmapPacker.cpp
)

# 头文件
set(HEADERS
    LightmapPacker.h
)

# 创建共享库
add_library(LightmapPacker SHARED ${SOURCES} ${HEADERS})

# 在Windows上使用.def文件
if(WIN32)
    target_link_options(LightmapPacker PRIVATE "/DEF:${DEF_FILE}")
endif()

# 包含目录
target_include_directories(LightmapPacker PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# 安装规则
install(TARGETS LightmapPacker
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(FILES ${HEADERS} DESTINATION include)

# 复制DLL到Python目录以便测试
add_custom_command(TARGET LightmapPacker POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy 
        $<TARGET_FILE:LightmapPacker>
        ${CMAKE_CURRENT_SOURCE_DIR}/
    COMMENT "复制DLL到Python目录"
)

# 添加测试目标
add_custom_target(run_python_test
    COMMAND python ${CMAKE_CURRENT_SOURCE_DIR}/python_example.py
    DEPENDS LightmapPacker
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "运行Python测试脚本"
)