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

struct LightMapInstanceGroup
{
    float scale = 1.0f;
    // 原始的矩形的宽度
    int source_rectangle_width = 0;
    int source_rectangle_height = 0;

    int texture_index = -1;
    // = source_rectangle_width * scale
    int rectangle_widht = 0;
    // = source_rectangle_height * scale
    int rectangle_height = 0;

    int group_instance_count = 0;
    std::vector<int> rectangles;

    LightMapInstanceGroup() = default;
    LightMapInstanceGroup(const LightMapInstanceGroup &) = default;
    LightMapInstanceGroup &operator=(const LightMapInstanceGroup &) = default;
    LightMapInstanceGroup(LightMapInstanceGroup &&) = default;
    LightMapInstanceGroup &operator=(LightMapInstanceGroup &&) = default;
    ~LightMapInstanceGroup() = default;

    LightMapInstanceGroup &operator=(const InputGroupData &other)
    {
        group_instance_count = other.rectangle_count;
        for (int i = 0; i < group_instance_count; i++)
        {
            rectangles.push_back(other.rectangle_id[i]);
        }
        source_rectangle_width = other.rectangle_width;
        source_rectangle_height = other.rectangle_height;
        return *this;
    }
};

// 使用TLF算法  顶部左对齐,因为在Vulkan中，纹理的坐标是(0,0)在左上角，所以需要从上到下，从左到右依次排列
// 以矩形为锚点，每次紧挨着目标矩形，从上到下，从左到右依次排列
// 放置就是搜索的过程，是否还有空余空间
// 一旦放下，就不会再拿出来了
struct LightMapTexture
{
    int texture_index = -1;
    // texture 一定是正方形的
    int texture_size = 0;

    std::vector<LightMapInstanceGroup *> groups;

    bool TryAddGroup(LightMapInstanceGroup &group)
    {
        return false;
    }

    // 一组矩形是否可以放入到纹理中, 如果group为nullptr，那么就只判断是否可以放入到大小为texture_size的纹理中
    static bool TryFitSize(int texture_size, int rectangle_width, int rectangle_height, int rectangle_count,
                           std::vector<LightMapInstanceGroup *> *groups)
    {

        // 0: 矩形宽度
        // 1: 矩形高度
        int* rectangles = nullptr;
        int pending_index = 0;
        if(groups == nullptr)
        {
            rectangles = new int[rectangle_count * 2];
        }
        else
        {
            pending_index = groups->size();
            rectangles = new int[(rectangle_count + groups->size()) * 2];
            for(int i = 0; i < groups->size(); ++i)
            {
                rectangles[i * 2] = (*groups)[i]->source_rectangle_width;
                rectangles[i * 2 + 1] = (*groups)[i]->source_rectangle_height;
            }
        }

        // 当前对角线的起始坐标
        int current_start_x = 0;
        int current_start_y = 0;
        // 当前对角线物体的宽度
        int current_line_width = 0;
        // 当前对角线物体的高度
        int current_line_height = 0;

        int current_width_x = 0;
        int current_width_y = 0;
        // 算法的大改示例如下
        // x 0 0 0
        // x 0 0 0
        // x 0 0 0
        // x x x 0
        // ========
        // x x 0 0
        // x x 0 0
        // x x x x
        // x x x x
        // 按照横，列的顺序一个个填充
        // 处于对角线上的那个矩形，定义了这行和这列的宽度
        // 这是货架算法 + BLF算法的结合
        for(int i = 0; i < rectangle_count; ++i)
        {
            
        }

        delete[] rectangles;
        return false;
    }
};

// 使用PIMPL模式
class LightmapPackerImpl
{
public:
    LightmapPackerImpl() : textureCount(0), packingEfficiency(0.0f) {}
    ~LightmapPackerImpl() {}

    int textureSize;
    // 一个矩形的最小宽度，低于此宽度报错
    int min_rectangle_width = 1;

    std::function<void(const char *)> log_callback;

    // 编码的效率
    float packingEfficiency;
    int textureCount;
    std::vector<OutputGroupData> results;

    std::vector<LightMapInstanceGroup> lightMapInstanceGroups;

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

    template <typename... Args>
    void Log(const char *format, Args &&...args)
    {
        if (log_callback)
        {
            char *message = char_merge(format, std::forward<Args>(args)...);
            log_callback(message);
            delete[] message;
        }
    }

    bool SetTextureSize(int texture_size)
    {
        textureSize = texture_size;
        return true;
    }

    bool AddGroup(InputGroupData *input_group_data)
    {
        LightMapInstanceGroup lightMapInstanceGroup;
        lightMapInstanceGroup = *input_group_data;
        lightMapInstanceGroups.push_back(std::move(lightMapInstanceGroup));

        Log("AddGroup: 组添加完成共有 %d 个矩形, 当前组数量: %d", input_group_data->rectangle_count, lightMapInstanceGroups.size());
        return true;
    }

    bool PackLightmaps()
    {
        int group_count = lightMapInstanceGroups.size();
        if (group_count == 0)
        {
            Log("PackLightmaps: 没有组");
            return true;
        }

        // 由大到小排序
        std::sort(lightMapInstanceGroups.begin(), lightMapInstanceGroups.end(), [](const LightMapInstanceGroup &a, const LightMapInstanceGroup &b)
                  { return a.source_rectangle_height > b.source_rectangle_height; });

        for (int i = 0; i < group_count; i++)
        {
            Log("PackLightmaps: 组 %d 宽度: %d 高度: %d", i, lightMapInstanceGroups[i].source_rectangle_width, lightMapInstanceGroups[i].source_rectangle_height);
        }

        // auto startTime = std::chrono::high_resolution_clock::now();

        // // 获取系统线程数
        // threadCount = std::thread::hardware_concurrency();
        // Log("使用线程数量: %d", threadCount);

        // // 模拟处理时间和结果
        // std::this_thread::sleep_for(std::chrono::seconds(1));

        // auto endTime = std::chrono::high_resolution_clock::now();
        // auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
        // Log("处理完成，耗时: %d 毫秒", duration.count());

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

    bool CaculateMaxGroupScale()
    {
        for (int i = 0; i < lightMapInstanceGroups.size(); i++)
        {
            float scale = 1.0f;
            LightMapInstanceGroup &group = lightMapInstanceGroups[i];

            int source_width = group.source_rectangle_width;
            int source_height = group.source_rectangle_height;
            int group_instance_count = group.group_instance_count;
            int current_width = source_width;
            int current_height = source_height;

            while (true)
            {
                current_width = source_width * scale;
                current_height = source_height * scale;

                if (current_width <= min_rectangle_width)
                {
                    Log("CaculateMaxGroupScale: 矩形%d 宽度 %d 低于最小宽度 %d", group.rectangles[0], current_width, min_rectangle_width);
                    return false;
                }

                // if (LightMapTexture::TryFitSize(textureSize, textureSize,
                //                                 current_width, current_height,
                //                                 group_instance_count))
                // {
                //     group.scale = scale;
                //     group.rectangle_widht = current_width;
                //     group.rectangle_height = current_height;
                //     break;
                // }
                scale *= 0.5f;
            }
        }
    }
};
// C语言接口
extern "C"
{
    void *CreateLightmapPacker()
    {
        return new LightmapPackerImpl();
    }

    void DestroyLightmapPacker(void *packer)
    {
        delete static_cast<LightmapPackerImpl *>(packer);
    }

    bool SetTextureSize(void *packer, int texture_size)
    {
        return static_cast<LightmapPackerImpl *>(packer)->SetTextureSize(texture_size);
    }

    bool AddGroup(void *packer, InputGroupData *input_group_data)
    {
        return static_cast<LightmapPackerImpl *>(packer)->AddGroup(input_group_data);
    }

    bool PackLightmaps(void *packer)
    {
        return static_cast<LightmapPackerImpl *>(packer)->PackLightmaps();
    }

    int GetTextureCount(void *packer)
    {
        return static_cast<LightmapPackerImpl *>(packer)->GetTextureCount();
    }

    float GetPackingEfficiency(void *packer)
    {
        return static_cast<LightmapPackerImpl *>(packer)->GetPackingEfficiency();
    }

    int GetResultCount(void *packer)
    {
        return static_cast<LightmapPackerImpl *>(packer)->GetResultCount();
    }

    int GetResult(void *packer, OutputGroupData *output_group_data)
    {
        return static_cast<LightmapPackerImpl *>(packer)->GetResult(output_group_data);
    }

    void TestLog(void *packer)
    {
        static_cast<LightmapPackerImpl *>(packer)->TestLog();
    }

    void SetLogCallBack(void *packer, void (*log_callback)(const char *message))
    {
        static_cast<LightmapPackerImpl *>(packer)->SetLogCallBack(log_callback);
    }
}
