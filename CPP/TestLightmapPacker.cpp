#include <iostream>
#include <string>
#include <chrono>
#include "LightmapPacker.h"

int main(int argc, char* argv[]) {
    std::cout << "=== LightmapPacker DLL测试程序 ===" << std::endl;
    
    // 解析命令行参数
    std::string jsonPath = "./current_scene_data_source.json";
    std::string lightmapPath = "./light/light_map";
    std::string outputPath = "./light/light_map/BigLightmap";
    bool useSimulatedAnnealing = true;
    
    // 处理命令行参数
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "--json" && i + 1 < argc) {
            jsonPath = argv[++i];
        } else if (arg == "--lightmap" && i + 1 < argc) {
            lightmapPath = argv[++i];
        } else if (arg == "--output" && i + 1 < argc) {
            outputPath = argv[++i];
        } else if (arg == "--algorithm" && i + 1 < argc) {
            std::string algorithm = argv[++i];
            useSimulatedAnnealing = (algorithm != "traditional");
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "用法: TestLightmapPacker [选项]" << std::endl;
            std::cout << "选项:" << std::endl;
            std::cout << "  --json PATH       指定JSON文件路径" << std::endl;
            std::cout << "  --lightmap PATH   指定灯光贴图目录路径" << std::endl;
            std::cout << "  --output PATH     指定输出目录路径" << std::endl;
            std::cout << "  --algorithm TYPE  指定算法类型 (simulated_annealing 或 traditional)" << std::endl;
            std::cout << "  --help, -h        显示此帮助信息" << std::endl;
            return 0;
        }
    }
    
    try {
        auto startTime = std::chrono::high_resolution_clock::now();
        
        // 创建LightmapPacker实例
        LightmapPacker packer;
        
        // 设置参数
        std::cout << "设置JSON文件路径: " << jsonPath << std::endl;
        if (!packer.setJsonPath(jsonPath.c_str())) {
            std::cerr << "设置JSON路径失败" << std::endl;
            return 1;
        }
        
        std::cout << "设置灯光贴图路径: " << lightmapPath << std::endl;
        if (!packer.setLightmapPath(lightmapPath.c_str())) {
            std::cerr << "设置灯光贴图路径失败" << std::endl;
            return 1;
        }
        
        std::cout << "设置输出路径: " << outputPath << std::endl;
        if (!packer.setOutputPath(outputPath.c_str())) {
            std::cerr << "设置输出路径失败" << std::endl;
            return 1;
        }
        
        // 执行打包
        std::cout << "开始打包灯光贴图，使用" 
                 << (useSimulatedAnnealing ? "模拟退火算法" : "传统算法") 
                 << "..." << std::endl;
        
        if (!packer.packLightmaps(useSimulatedAnnealing)) {
            std::cerr << "打包失败" << std::endl;
            return 1;
        }
        
        // 获取结果
        std::cout << "打包成功！生成了 " << packer.getTextureCount() << " 个纹理" << std::endl;
        std::cout << "打包效率: " << packer.getPackingEfficiency() * 100 << "%" << std::endl;
        
        const auto& results = packer.getResults();
        std::cout << "总共处理了 " << results.size() << " 个物体" << std::endl;
        
        // 显示前5个结果作为示例
        std::cout << "\n结果示例 (前5个):" << std::endl;
        for (int i = 0; i < std::min(5, static_cast<int>(results.size())); ++i) {
            const auto& result = results[i];
            std::cout << "物体 " << i << ": " << result.name 
                     << ", 纹理: " << result.texture_index 
                     << ", 位置: (" << result.position.first << "," << result.position.second << ")"
                     << ", 尺寸: " << result.size.first << "x" << result.size.second 
                     << std::endl;
        }
        
        auto endTime = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
        std::cout << "\n总耗时: " << duration.count() << " 毫秒" << std::endl;
        
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "发生异常: " << e.what() << std::endl;
        return 1;
    }
} 