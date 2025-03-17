#pragma once
#ifndef LIGHTMAP_PACKER_EXPORTS
#define LIGHTMAP_PACKER_EXPORTS
#endif

#ifdef _WIN32
#ifdef LIGHTMAP_PACKER_EXPORTS
#define LIGHTMAP_API __declspec(dllexport)
#else
#define LIGHTMAP_API __declspec(dllimport)
#endif
#else
#define LIGHTMAP_API
#endif

#include <memory>

class LightmapPackerImpl;

#pragma pack(push, 4)

struct LIGHTMAP_API InputGroupData
{
    int rectangle_count;

    int rectangle_width;
    int rectangle_height;

    // 所有的矩形的id，在python侧声明，数量 = rectangle_count
    int* rectangle_id;
};

struct LIGHTMAP_API OutputGroupData
{
    // 当前Group使用的纹理的index
    int texture_index;
    // 当前Group使用的缩放比例
    float scale;

    // 当前Group使用的矩形的宽度 = 原始的rectangle_width * scale
    int single_rectangle_width;
    // 当前Group使用的矩形的高度 = 原始的rectangle_height * scale
    int single_rectangle_height;

    struct SingleOutPutRectangle{
        // 当前Group使用的矩形在纹理中的x坐标
        int position_x;
        // 当前Group使用的矩形在纹理中的y坐标
        int position_y;
        // 当前Group使用的矩形的id
        int rectangle_id;
    };

    // 当前Group使用的矩形的数量
    int group_instance_count;

    // 当前group的每一个矩形 数量 = group_instance_count
    SingleOutPutRectangle* rectangles;
};
#pragma pack(pop)

/**
 * 灯光贴图打包器
 */
class LIGHTMAP_API LightmapPacker
{
public:
    LightmapPacker();
    ~LightmapPacker();

    /**
     * 设置纹理的大小
     * @param texture_size 纹理的大小(像素)
     * @return 是否成功
     */
    bool SetTextureSize(int texture_size);

    /**
     * 添加一个Group
     * @param group_key 当前Group的key
     * @param group_json_data 当前Group的JSON数据(原始的JSON数据)
     * @return 是否成功
     */
    bool AddGroup();

    /**
     * 打包灯光贴图
     * @return 是否成功
     */
    bool PackLightmaps();

    /**
     * 获取打包的纹理数量
     * @return 打包的纹理数量
     */
    int GetTextureCount() const;

    /**
     * 获取打包的效率
     * @return 打包的效率
     */
    float GetPackingEfficiency() const;

    /**
     * 获取打包的结果数量
     * @return 打包的结果数量
     */
    int GetResultCount() const;

    int GetResult(OutputGroupData* output_group_data) const;

    void TestLog() const;

    /**
     * 设置日志回调函数
     * @param log_callback 回调函数指针
     */
    void SetLogCallBack(void (*log_callback)(const char *message));

private:
    std::unique_ptr<LightmapPackerImpl> pImpl; // PIMPL模式
};

// C语言接口
extern "C"
{
    /**
     * 创建LightmapPacker
     * @return LightmapPacker
     */
    LIGHTMAP_API void *CreateLightmapPacker();

    /**
     * 销毁LightmapPacker
     * @param packer LightmapPacker
     */
    LIGHTMAP_API void DestroyLightmapPacker(void *packer);

    /**
     * 设置纹理的大小
     * @param packer LightmapPacker
     * @param texture_size 纹理的大小(像素)
     * @return 是否成功
     */
    LIGHTMAP_API bool SetTextureSize(void *packer, int texture_size);

    /**
     * 添加一个Group
     * @param packer LightmapPacker
     * @param group_key 当前Group的key
     * @param group_json_data 当前Group的JSON数据(原始的JSON数据)
     * @return 是否成功
     */
    LIGHTMAP_API bool AddGroup(void *packer);

    /**
     * 打包灯光贴图
     * @param packer LightmapPacker
     * @param use_simulated_annealing 是否使用模拟退火算法
     * @return 是否成功
     */
    LIGHTMAP_API bool PackLightmaps(void *packer);

    /**
     * 获取打包的纹理数量
     * @param packer LightmapPacker
     * @return 打包的纹理数量
     */
    LIGHTMAP_API int GetTextureCount(void *packer);

    /**
     * 获取打包的效率(0.0-1.0)
     * @param packer LightmapPacker
     * @return 打包的效率
     */
    LIGHTMAP_API float GetPackingEfficiency(void *packer);

    /**
     * 获取打包的结果数量
     * @param packer LightmapPacker
     * @return 打包的结果数量
     */
    LIGHTMAP_API int GetResultCount(void *packer);

    /**
     */
    LIGHTMAP_API int GetResult(void *packer, OutputGroupData* output_group_data);

    /**
     * 测试日志
     * @param packer LightmapPacker
     */
    LIGHTMAP_API void TestLog(void *packer);

    LIGHTMAP_API void SetLogCallBack(void *packer, void (*log_callback)(const char *message));
}
