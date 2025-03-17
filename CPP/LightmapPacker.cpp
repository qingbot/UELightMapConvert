#include "LightmapPacker.h"
#include <vector>
#include <string>
#include <thread>
#include <memory>
#include <iostream>
#include <fstream>
#include <algorithm>
#include <chrono>
#include <mutex>
#include <atomic>
#include <future>
#include <filesystem>
#include <cstring> 
#include <functional>

namespace fs = std::filesystem;

template <typename... Args>
char *char_merge(const char *left, Args &&...args)
{
    int length = snprintf(nullptr, 0, left, std::forward<Args>(args)...);
    char *result = new char[length + 1];
    snprintf(result, length + 1, left, std::forward<Args>(args)...);
    return result;
}

// 使用PIMPL模式
class LightmapPackerImpl
{
public:
    LightmapPackerImpl() : textureCount(0), packingEfficiency(0.0f) {}
    ~LightmapPackerImpl() {}

    int textureSize;

    std::function<void(const char *)> log_callback;

    // 编码的效率
    float packingEfficiency;
    int textureCount;
    std::vector<OutputGroupData> results;

    // 使用的线程数量
    unsigned int threadCount;

    void SetLogCallBack(std::function<void(const char *)> call_back)
    {
        log_callback = call_back;
    }

    void Log(const char *message)
    {
        if (log_callback)
        {
            log_callback(message);
        }
    }

    template<typename... Args>
    void Log(const char* format, Args&&... args)
    {
        if(log_callback)
        {
            char* message = char_merge(format, std::forward<Args>(args)...);
            log_callback(message);
            delete[] message;
        }
    }

    bool SetTextureSize(int texture_size)
    {
        textureSize = texture_size;
        return true;
    }

    bool AddGroup()
    {
        
        return true;
    }

    bool PackLightmaps()
    {
        auto startTime = std::chrono::high_resolution_clock::now();

        // 获取系统线程数
        threadCount = std::thread::hardware_concurrency();
        Log("使用线程数量: %d", threadCount);

        // TODO: 实现实际的灯光贴图打包算法
        // 1. 加载JSON数据
        // 2. 按参数分组
        // 3. 应用模拟退火或传统算法进行打包
        // 4. 保存结果

        // 模拟处理时间和结果
        std::this_thread::sleep_for(std::chrono::seconds(1));

        auto endTime = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
        Log("处理完成，耗时: %d 毫秒", duration.count());

        return true;
    }

    int GetTextureCount() const
    {
        return textureCount;
    }

    float GetPackingEfficiency() const
    {
        return packingEfficiency;
    }

    int GetResultCount() const
    {
        return results.size();
    }

    int GetResult(OutputGroupData *output_group_data) const
    {
        return -1;
    }

    void TestLog()
    {
        Log("测试日志");
        Log("测试日志 %d", 123);
        Log("测试日志 %s", "Hello");
        Log("测试日志 %d %s", 123, "Hello");
    }

};

LightmapPacker::LightmapPacker() : pImpl(std::make_unique<LightmapPackerImpl>()) {}

LightmapPacker::~LightmapPacker() = default;

bool LightmapPacker::SetTextureSize(int texture_size)
{
    return pImpl->SetTextureSize(texture_size);
}

bool LightmapPacker::AddGroup()
{
    return pImpl->AddGroup();
}

bool LightmapPacker::PackLightmaps()
{
    return pImpl->PackLightmaps();
}

int LightmapPacker::GetTextureCount() const
{
    return pImpl->GetTextureCount();
}

float LightmapPacker::GetPackingEfficiency() const
{
    return pImpl->GetPackingEfficiency();
}

int LightmapPacker::GetResultCount() const
{
    return pImpl->GetResultCount();
}

int LightmapPacker::GetResult(OutputGroupData *output_group_data) const
{
    return pImpl->GetResult(output_group_data);
}

void LightmapPacker::TestLog() const
{
    pImpl->TestLog();
}

void LightmapPacker::SetLogCallBack(void (*log_callback)(const char *message))
{
    pImpl->SetLogCallBack(log_callback);
}

// C语言接口
extern "C"
{
    void *CreateLightmapPacker()
    {
        return new LightmapPacker();
    }

    void DestroyLightmapPacker(void *packer)
    {
        delete static_cast<LightmapPacker *>(packer);
    }

    bool SetTextureSize(void *packer, int texture_size)
    {
        return static_cast<LightmapPacker *>(packer)->SetTextureSize(texture_size);
    }

    bool AddGroup(void *packer)
    {
        return static_cast<LightmapPacker *>(packer)->AddGroup();
    }

    bool PackLightmaps(void *packer)
    {
        return static_cast<LightmapPacker *>(packer)->PackLightmaps();
    }

    int GetTextureCount(void *packer)
    {
        return static_cast<LightmapPacker *>(packer)->GetTextureCount();
    }

    float GetPackingEfficiency(void *packer)
    {
        return static_cast<LightmapPacker *>(packer)->GetPackingEfficiency();
    }

    int GetResultCount(void *packer)
    {
        return static_cast<LightmapPacker *>(packer)->GetResultCount();
    }

    int GetResult(void *packer, OutputGroupData *output_group_data)
    {
        return static_cast<LightmapPacker *>(packer)->GetResult(output_group_data);
    }

    void TestLog(void *packer)
    {
        static_cast<LightmapPacker *>(packer)->TestLog();
    }

    void SetLogCallBack(void *packer, void (*log_callback)(const char *message))
    {
        static_cast<LightmapPacker *>(packer)->SetLogCallBack(log_callback);
    }
}
