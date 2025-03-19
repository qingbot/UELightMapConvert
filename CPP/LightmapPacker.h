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
    int *rectangle_id;
};

struct SingleOutPutRectangle
{
    // 当前Group使用的矩形在纹理中的x坐标
    int position_x;
    // 当前Group使用的矩形在纹理中的y坐标
    int position_y;
    int width;
    int height;
    // 当前Group使用的矩形的id
    int rectangle_id;
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

    // 当前Group使用的矩形的数量
    int group_instance_count;

    // 当前group的每一个矩形 数量 = group_instance_count
    SingleOutPutRectangle *rectangles;
};

struct LIGHTMAP_API OutLightMapTexture
{
    // 当前纹理的index
    int texture_index;

    // 当前纹理的宽度
    int texture_width;

    // 当前纹理的高度
    int texture_height;

    // 当前纹理的矩形数量
    int rectangle_count;

    // 当前纹理的矩形 数量 = rectangle_count
    SingleOutPutRectangle *rectangles;
};

#pragma pack(pop)

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
    LIGHTMAP_API bool AddGroup(void *packer, InputGroupData *input_group_data);

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

    // 获取对应纹理，拥有的矩形的数量，返回-1则表示没有这张图，获取结束
    LIGHTMAP_API int GetTextureRectangleCount(void *packer,int textureID);

    // 获取对应纹理，拥有的矩形
    LIGHTMAP_API bool GetTextureResult(void *packer, int textureID, OutLightMapTexture *output_group_data);

    /**
     * 测试日志
     * @param packer LightmapPacker
     */
    LIGHTMAP_API void TestLog(void *packer);

    LIGHTMAP_API void SetLogCallBack(void *packer, void (*log_callback)(const char *message));
}
