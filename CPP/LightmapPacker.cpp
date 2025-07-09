#include "LightmapPacker.h"
#include <algorithm>
#include <assert.h>
#include <atomic>
#include <chrono>
#include <cstring>
#include <fstream>
#include <functional>
#include <future>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

using std::vector;

template <typename... Args> char *char_merge(const char *left, Args &&...args) {
  int length = snprintf(nullptr, 0, left, std::forward<Args>(args)...);
  char *result = new char[length + 1];
  snprintf(result, length + 1, left, std::forward<Args>(args)...);
  return result;
}

std::function<void(const char *)> global_log_callback;

template <typename... Args> void GlobalLog(const char *format, Args &&...args) {
  if (global_log_callback) {
    char *message = char_merge(format, std::forward<Args>(args)...);
    global_log_callback(message);
    delete[] message;
  }
}

struct LightMapInstanceGroup {
  float scale = 1.0f;
  // 原始的矩形的宽度
  int source_rectangle_width = 0;
  int source_rectangle_height = 0;

  // int texture_index = -1;
  // = source_rectangle_width * scale
  int rectangle_width = 0;
  // = source_rectangle_height * scale
  int rectangle_height = 0;

  int group_instance_count = 0;
  // 矩形的id
  std::vector<int> rectangles_id;

  LightMapInstanceGroup() = default;
  LightMapInstanceGroup(const LightMapInstanceGroup &) = default;
  LightMapInstanceGroup &operator=(const LightMapInstanceGroup &) = default;
  LightMapInstanceGroup(LightMapInstanceGroup &&) = default;
  LightMapInstanceGroup &operator=(LightMapInstanceGroup &&) = default;
  ~LightMapInstanceGroup() = default;

  LightMapInstanceGroup &operator=(const InputGroupData &other) {
    group_instance_count = other.rectangle_count;
    for (int i = 0; i < group_instance_count; i++) {
      rectangles_id.push_back(other.rectangle_id[i]);
    }
    scale = 1.0f;
    source_rectangle_width = other.rectangle_width;
    source_rectangle_height = other.rectangle_height;
    rectangle_width = source_rectangle_width * scale;
    rectangle_height = source_rectangle_height * scale;
    return *this;
  }
};

// 被LightmapTexture持有, 表示一个lightmap的矩形
struct SingleResultLightMapRectangle {
  int position_x = 0;
  int position_y = 0;
  int width = 0;
  int height = 0;
  int rectangle_id = 0;
  LightMapInstanceGroup *group = nullptr;

  SingleResultLightMapRectangle() = default;
  SingleResultLightMapRectangle(int position_x, int position_y, int width,
                                int height, int rectangle_id,
                                LightMapInstanceGroup *group) {
    this->position_x = position_x;
    this->position_y = position_y;
    this->width = width;
    this->height = height;
    this->rectangle_id = rectangle_id;
    this->group = group;
  }
};

// 专门用以计算打包的矩形，表示空白区域
// 被对角线持有
struct RectangleForPacking {
  int position_x = 0;
  int position_y = 0;
  int width = 0;
  int height = 0;

  // 尝试获取一个最合适的空白区域, 优先找面积最小的，其次是位置最靠近左下角的
  // 返回index， -1表示没有找到
  static int
  try_get_most_suitable_place(int width, int height,
                              vector<RectangleForPacking> &remaining_places) {
    int min_area = INT_MAX;
    int position_x = -1;
    int position_y = -1;
    int index = -1;
    // 最靠近左下角的，面积最小的
    for (int i = 0; i < remaining_places.size(); i++) {
      RectangleForPacking &place = remaining_places[i];
      if (place.width >= width && place.height >= height) {
        int area = place.width * place.height;
        if (area < min_area) {
          min_area = area;
          position_x = place.position_x;
          position_y = place.position_y;
          index = i;
        } else if (area == min_area) {
          if (place.position_x < position_x) {
            position_x = place.position_x;
            position_y = place.position_y;
            index = i;
          } else if (place.position_x == position_x &&
                     place.position_y < position_y) {
            position_y = place.position_y;
            index = i;
          }
        }
      }
    }
    return index;
  }

  // 尝试获取一个空白区域
  // 需要的宽度，高度
  // 剩余的空白区域
  // 如果返回true,则表示分割出来了一个空白区域
  // 如果返回false,则表示没有分割出来空白区域
  static bool try_get_place(int width, int height,
                            vector<RectangleForPacking> &remaining_places,
                            RectangleForPacking &result) {
    int index = try_get_most_suitable_place(width, height, remaining_places);
    if (index == -1) {
      return false;
    }
    RectangleForPacking place = remaining_places[index];
    assert(place.width >= width && place.height >= height);
    remaining_places.erase(remaining_places.begin() + index);

    // 将目标区域分割出来，添加到result中，剩余区域裁切为多个矩形，添加到remaining_places中
    if (place.width == width && place.height == height) {
      result = place;
      return true;
    }

    // 以下是这种情况
    // 0 0
    // 0 0
    // x 0
    // ==========
    // 1 1
    // 1 1
    // x 0
    // +++++++++++++++++
    // 0 0 0
    // x 0 0
    // ==========
    // 1 0 0
    // x 0 0
    // 有以上两种情况
    // 将x裁切出来,将剩余区域裁切为两个矩形
    // 裁切为 0 和 1 两个矩形
    // 如果剩余区域的宽度大于高度，就横着切，否则竖着切
    // 裁切出目标区域
    result.position_x = place.position_x;
    result.position_y = place.position_y;
    result.width = width;
    result.height = height;

    auto check_size_func = [](const RectangleForPacking &a) {
      return a.width > 0 && a.height > 0;
    };
    RectangleForPacking remaining_place0;
    RectangleForPacking remaining_place1;
    if (place.width - width > place.height - height) {
      // 横着切
      remaining_place0.position_x = place.position_x + width;
      remaining_place0.position_y = place.position_y;
      remaining_place0.width = place.width - width;
      remaining_place0.height = place.height;

      remaining_place1.position_x = place.position_x;
      remaining_place1.position_y = place.position_y + height;
      remaining_place1.width = width;
      remaining_place1.height = place.height - height;
    } else {
      // 竖着切
      remaining_place0.position_x = place.position_x + width;
      remaining_place0.position_y = place.position_y;
      remaining_place0.width = place.width - width;
      remaining_place0.height = height;

      remaining_place1.position_x = place.position_x;
      remaining_place1.position_y = place.position_y + height;
      remaining_place1.width = place.width;
      remaining_place1.height = place.height - height;
    }
    if (check_size_func(remaining_place0)) {
      remaining_places.push_back(remaining_place0);
    }

    if (check_size_func(remaining_place1)) {
      remaining_places.push_back(remaining_place1);
    }

    return true;
  }
};

// 使用TLF算法
// 顶部左对齐,因为在Vulkan中，纹理的坐标是(0,0)在左上角，所以需要从上到下，从左到右依次排列
// 以矩形为锚点，每次紧挨着目标矩形，从上到下，从左到右依次排列
// 放置就是搜索的过程，是否还有空余空间
// 一旦放下，就不会再拿出来了
struct LightMapTexture {
  // 对角线信息
  struct Diagonal {
    // 处于对角线上，起始矩形的宽度
    int width;
    int height;

    // 处于对角线上的矩形，在纹理中的位置
    int position_x = 0;
    int position_y = 0;

    // 归属于当前对角线的矩形
    vector<SingleResultLightMapRectangle> rectangles;

    // 空白区域
    vector<RectangleForPacking> rectangles_row;
    vector<RectangleForPacking> rectangles_column;
  };

  int texture_index = -1;
  // texture 一定是正方形的
  int texture_size = 0;

  // 这里面存着当前texture里面所有的矩形
  vector<Diagonal> diagonals;

  bool TryAddGroup(LightMapInstanceGroup &group) {
    return LightMapTexture::TryAdd(&group, this);
  }

private:
  // 获取一个对角线，并设置中心
  // 结果，对角线中心，持有此对角线的贴图，矩形id，对角线的位置
  static bool GetADiagonalAndSetCenter(Diagonal &diagonal,
                                       LightMapInstanceGroup *center,
                                       LightMapTexture *lightMapTexture,
                                       int rectangle_index, int position_x,
                                       int position_y) {
    if (position_x + center->rectangle_width > lightMapTexture->texture_size ||
        position_y + center->rectangle_height > lightMapTexture->texture_size) {
      return false;
    }

    diagonal.width = center->rectangle_width;
    diagonal.height = center->rectangle_height;
    diagonal.position_x = position_x;
    diagonal.position_y = position_y;
    diagonal.rectangles.push_back(SingleResultLightMapRectangle(
        position_x, position_y, center->rectangle_width,
        center->rectangle_height, center->rectangles_id[rectangle_index],
        center));

    LightMapInstanceGroup *single_texture = center;

    auto check_size_func = [](const RectangleForPacking &a) {
      return a.width > 0 && a.height > 0;
    };

    // 先横 再列
    RectangleForPacking rectangle_for_packing_row;
    rectangle_for_packing_row.position_x =
        position_x + single_texture->rectangle_width;
    rectangle_for_packing_row.position_y = position_y;
    rectangle_for_packing_row.width =
        lightMapTexture->texture_size - rectangle_for_packing_row.position_x;
    rectangle_for_packing_row.height = single_texture->rectangle_height;

    RectangleForPacking rectangle_for_packing_column;
    rectangle_for_packing_column.position_x = position_x;
    rectangle_for_packing_column.position_y =
        position_y + single_texture->rectangle_height;
    rectangle_for_packing_column.width = single_texture->rectangle_width;
    rectangle_for_packing_column.height =
        lightMapTexture->texture_size - rectangle_for_packing_column.position_y;

    if (check_size_func(rectangle_for_packing_row)) {
      diagonal.rectangles_row.push_back(rectangle_for_packing_row);
    }
    if (check_size_func(rectangle_for_packing_column)) {
      diagonal.rectangles_column.push_back(rectangle_for_packing_column);
    }

    return true;
  }

public:
  // 尝试将当前的Group塞入到lightMapTexture中，如果塞不下，则什么都没发生，如果塞下了，则直接塞入Texture中
  static bool TryAdd(LightMapInstanceGroup *group,
                     LightMapTexture *lightMapTexture) {
    // 对角线上所有的矩形
    if (group == nullptr || lightMapTexture == nullptr) {
      return false;
    }
    if (group->group_instance_count == 0) {
      return true;
    }
    vector<Diagonal> diagonals = lightMapTexture->diagonals;
    // 算法的示例如下
    // 0  0  0  0
    // 0  0  0  0
    // 0  0  0  0
    // x  0  0  0
    // =============
    // x  0  0  0
    // x  0  0  0
    // x  0  0  0
    // x  x  x  0
    // =============
    // x  x  0  0
    // x  x  0  0
    // x  x  x  x
    // x  x  x  x
    // 按照横，列的顺序一个个填充
    // 处于对角线上的那个矩形，定义了这行和这列的宽度
    // 这是货架算法 + BLF算法的结合
    LightMapInstanceGroup *single_texture = group;
    for (int i = 0; i < group->group_instance_count; ++i) {
      // 如果是一张新开的图，那么就创建一个对角线
      if (diagonals.size() == 0) {
        Diagonal diagonal;
        if (GetADiagonalAndSetCenter(diagonal, single_texture, lightMapTexture,
                                     i, 0, 0)) {
          diagonals.push_back(diagonal);
        } else {
          // 第一个矩形都放不下
          return false;
        }
      } else {
        Diagonal &diagonal = diagonals.back();

        RectangleForPacking rectangle_for_packing;
        // 先尝试横着放，如果横着放不下，再尝试竖着放
        if (RectangleForPacking::try_get_place(single_texture->rectangle_width,
                                               single_texture->rectangle_height,
                                               diagonal.rectangles_row,
                                               rectangle_for_packing) ||
            RectangleForPacking::try_get_place(single_texture->rectangle_height,
                                               single_texture->rectangle_width,
                                               diagonal.rectangles_column,
                                               rectangle_for_packing)) {
          // 找到了一个位置
          diagonal.rectangles.push_back(SingleResultLightMapRectangle(
              rectangle_for_packing.position_x,
              rectangle_for_packing.position_y, rectangle_for_packing.width,
              rectangle_for_packing.height, single_texture->rectangles_id[i],
              single_texture));
        } else {
          // 如果横竖都放不下，那么就创建一个新的对角线
          Diagonal new_diagonal;
          if (GetADiagonalAndSetCenter(new_diagonal, single_texture,
                                       lightMapTexture, i,
                                       diagonal.position_x + diagonal.width,
                                       diagonal.position_y + diagonal.height)) {
            diagonals.push_back(new_diagonal);
          } else {
            // 如果没有对角线的空间了，那么就返回false，那就是真的放不下了
            return false;
          }
        }
      }
    }

    lightMapTexture->diagonals = diagonals;
    return true;
  }
};

// 使用PIMPL模式
class LightmapPackerImpl {
public:
  LightmapPackerImpl() {}
  ~LightmapPackerImpl() {}

  int textureSize = 2048;
  // 一个矩形的最小宽度，低于此宽度报错
  int min_rectangle_width = 1;

  std::function<void(const char *)> log_callback;

  std::vector<OutputGroupData> results;

  std::vector<LightMapInstanceGroup> lightMapInstanceGroups;

  vector<LightMapTexture *> lightMapTextures;

  // 使用的线程数量
  unsigned int threadCount;

  void SetLogCallBack(std::function<void(const char *)> call_back) {
    log_callback = call_back;
    global_log_callback = call_back;
  }

  void Log(const char *message) {
    if (log_callback) {
      log_callback(message);
    }
  }

  template <typename... Args> void Log(const char *format, Args &&...args) {
    if (log_callback) {
      char *message = char_merge(format, std::forward<Args>(args)...);
      log_callback(message);
      delete[] message;
    }
  }

  bool SetTextureSize(int texture_size) {
    textureSize = texture_size;
    return true;
  }

  bool AddGroup(InputGroupData *input_group_data) {
    LightMapInstanceGroup lightMapInstanceGroup;
    lightMapInstanceGroup = *input_group_data;
    lightMapInstanceGroups.push_back(std::move(lightMapInstanceGroup));

    Log("AddGroup: 组添加完成共有 %d 个矩形,宽度: %d 高度: %d 当前组数量: %d",
        input_group_data->rectangle_count, input_group_data->rectangle_width,
        input_group_data->rectangle_height, lightMapInstanceGroups.size());
    return true;
  }

  bool PackLightmaps() {
    int group_count = lightMapInstanceGroups.size();
    if (group_count == 0) {
      Log("PackLightmaps: 没有组");
      return true;
    }

    if (!CaculateMaxGroupScale()) {
      Log("PackLightmaps: 计算最大缩放失败");
      return false;
    }

    // 由大到小排序
    std::sort(
        lightMapInstanceGroups.begin(), lightMapInstanceGroups.end(),
        [](const LightMapInstanceGroup &a, const LightMapInstanceGroup &b) {
          return a.rectangle_width > b.rectangle_width;
        });

    Log("PackLightmaps: 对以下组进行打包, 组数量: %d", group_count);
    for (int i = 0; i < group_count; i++) {
      Log("PackLightmaps: 组 %d 宽度: %d 高度: %d 数量: %d", i,
          lightMapInstanceGroups[i].source_rectangle_width,
          lightMapInstanceGroups[i].source_rectangle_height,
          lightMapInstanceGroups[i].group_instance_count);
    }

    Log("PackLightmaps: 开始打包");

    int texture_id = 0;
    LightMapTexture *first_texture = new LightMapTexture();
    first_texture->texture_size = textureSize;
    first_texture->texture_index = texture_id++;
    lightMapTextures.push_back(first_texture);

    for (int i = 0; i < group_count; i++) {
      bool is_success = false;
      // 先尝试不缩放放入已有的纹理中
      LightMapInstanceGroup &current_group = lightMapInstanceGroups[i];
      for (int j = 0; j < lightMapTextures.size(); j++) {
        LightMapTexture *texture = lightMapTextures[j];
        if (texture->TryAddGroup(current_group)) {
          Log("PackLightmaps: 组 %d 打包完成，放入纹理 %d", i,
              texture->texture_index);
          is_success = true;
          break;
        }
      }
      // 放入新的纹理中
      if (!is_success) {
        LightMapTexture *new_texture = new LightMapTexture();
        new_texture->texture_size = textureSize;
        new_texture->texture_index = texture_id++;
        if (new_texture->TryAddGroup(current_group)) {
          Log("PackLightmaps: 组 %d 打包完成，放入新的纹理 %d", i,
              new_texture->texture_index);
          lightMapTextures.push_back(new_texture);
        } else {
          Log("PackLightmaps: 组 %d 打包失败", i);
          return false;
        }
      }
    }

    Log("PackLightmaps: 打包完成，共有 %d 个纹理", lightMapTextures.size());
    // auto startTime = std::chrono::high_resolution_clock::now();

    // // 获取系统线程数
    // threadCount = std::thread::hardware_concurrency();
    // Log("使用线程数量: %d", threadCount);

    // // 模拟处理时间和结果
    // std::this_thread::sleep_for(std::chrono::seconds(1));

    // auto endTime = std::chrono::high_resolution_clock::now();
    // auto duration =
    // std::chrono::duration_cast<std::chrono::milliseconds>(endTime -
    // startTime); Log("处理完成，耗时: %d 毫秒", duration.count());

    return true;
  }

  // 按照区域打包，同一个区域的lightmap打包到同一个纹理中，不会复用其他区域的纹理
  // 若lightmap放不下，则同一个区域内的所有lightmap都会被缩小
  bool PackSingleLightmap() {
    int group_count = lightMapInstanceGroups.size();
    if (group_count == 0) {
      Log("PackSingleLightmap: 没有需要打包的组");
      return true;
    }

    // 由大到小排序
    std::sort(
        lightMapInstanceGroups.begin(), lightMapInstanceGroups.end(),
        [](const LightMapInstanceGroup &a, const LightMapInstanceGroup &b) {
          return a.rectangle_width > b.rectangle_width;
        });

    float current_scale = 1.0f;

    auto max_value = [](float a, float b) { return a > b ? a : b; };

    // 尝试将所有的物体放入同一个纹理中
    while (true) {
      LightMapTexture *first_texture = new LightMapTexture();
      first_texture->texture_size = textureSize;
      first_texture->texture_index = 0;

      bool is_success = true;
      // 尝试把所有的物体都塞入一个纹理中
      for (int i = 0; i < group_count; i++) {
        LightMapInstanceGroup &current_group = lightMapInstanceGroups[i];
        current_group.rectangle_width =
            max_value(current_group.source_rectangle_width * current_scale, 1);
        current_group.rectangle_height =
            max_value(current_group.source_rectangle_height * current_scale, 1);

        LightMapTexture *texture = first_texture;
        if (texture->TryAddGroup(current_group)) {
        } else {
          is_success = false;
          break;
        }
      }

      if (is_success) {
        lightMapTextures.push_back(first_texture);
        break;
      }

      delete first_texture;
      current_scale *= 0.5f;
      // 如果一个32 * 32的纹理被压缩到1 * 1，都还放不下，则失败
      if (current_scale < (1.0f / 32.0f)) {
        Log("PackSingleLightmap: 所有物体都放不下，失败");
        return false;
      }
    }

    return true;
  }

  int GetTextureCount() const { return lightMapTextures.size(); }

  float GetPackingEfficiency() const { return 1.0f; }

  int GetTextureRectangleCount(int textureID) const {
    if (textureID < 0 || textureID >= lightMapTextures.size()) {
      return -1;
    }
    int rectangle_count = 0;
    for (int i = 0; i < lightMapTextures[textureID]->diagonals.size(); i++) {
      rectangle_count +=
          lightMapTextures[textureID]->diagonals[i].rectangles.size();
    }
    return rectangle_count;
  }

  bool GetTextureResult(int textureID,
                        OutLightMapTexture *output_group_data) const {
    if (textureID < 0 || textureID >= lightMapTextures.size()) {
      return false;
    }

    LightMapTexture *texture = lightMapTextures[textureID];
    output_group_data->texture_index = texture->texture_index;
    output_group_data->texture_width = texture->texture_size;
    output_group_data->texture_height = texture->texture_size;

    int rectangle_count = GetTextureRectangleCount(textureID);
    output_group_data->rectangle_count = rectangle_count;
    int index = 0;
    for (int i = 0; i < texture->diagonals.size(); i++) {
      for (int j = 0; j < texture->diagonals[i].rectangles.size(); j++) {
        SingleResultLightMapRectangle &rectangle =
            texture->diagonals[i].rectangles[j];
        SingleOutPutRectangle &output_rectangle =
            output_group_data->rectangles[index];
        output_rectangle.position_x = rectangle.position_x;
        output_rectangle.position_y = rectangle.position_y;
        output_rectangle.width = rectangle.width;
        output_rectangle.height = rectangle.height;
        output_rectangle.rectangle_id = rectangle.rectangle_id;
        index++;
      }
    }
    return true;
  }

  void TestLog() {
    Log("测试日志");
    Log("测试日志 %d", 123);
    Log("测试日志 %s", "Hello");
    Log("测试日志 %d %s", 123, "Hello");
  }

  //
  bool CaculateMaxGroupScale() {
    for (int i = 0; i < lightMapInstanceGroups.size(); i++) {
      LightMapInstanceGroup &current_group = lightMapInstanceGroups[i];
      float scale = 1.0f;
      while (true) {
        if (current_group.source_rectangle_width * scale <
                min_rectangle_width ||
            current_group.source_rectangle_height * scale <
                min_rectangle_width) {
          Log("PackLightmaps: 组 %d 宽度 %d 高度 %d 低于最小宽度 %d", i,
              current_group.source_rectangle_width,
              current_group.source_rectangle_height, min_rectangle_width);
          return false;
        }
        current_group.scale = scale;
        current_group.rectangle_width =
            current_group.source_rectangle_width * scale;
        current_group.rectangle_height =
            current_group.source_rectangle_height * scale;

        LightMapTexture *new_texture = new LightMapTexture();
        new_texture->texture_size = textureSize;
        new_texture->texture_index = -1;
        if (new_texture->TryAddGroup(current_group)) {
          delete new_texture;
          break;
        }
        delete new_texture;
        scale *= 0.5f;
      }
    }
    return true;
  }
};

// C语言接口
extern "C" {
void *CreateLightmapPacker() { return new LightmapPackerImpl(); }

void DestroyLightmapPacker(void *packer) {
  delete static_cast<LightmapPackerImpl *>(packer);
}

bool SetTextureSize(void *packer, int texture_size) {
  return static_cast<LightmapPackerImpl *>(packer)->SetTextureSize(
      texture_size);
}

bool AddGroup(void *packer, InputGroupData *input_group_data) {
  return static_cast<LightmapPackerImpl *>(packer)->AddGroup(input_group_data);
}

bool PackLightmaps(void *packer) {
  return static_cast<LightmapPackerImpl *>(packer)->PackLightmaps();
}

bool PackSingleLightmap(void *packer) {
  return static_cast<LightmapPackerImpl *>(packer)->PackSingleLightmap();
}

int GetTextureCount(void *packer) {
  return static_cast<LightmapPackerImpl *>(packer)->GetTextureCount();
}

float GetPackingEfficiency(void *packer) {
  return static_cast<LightmapPackerImpl *>(packer)->GetPackingEfficiency();
}

int GetTextureRectangleCount(void *packer, int textureID) {
  return static_cast<LightmapPackerImpl *>(packer)->GetTextureRectangleCount(
      textureID);
}

bool GetTextureResult(void *packer, int textureID,
                      OutLightMapTexture *output_group_data) {
  return static_cast<LightmapPackerImpl *>(packer)->GetTextureResult(
      textureID, output_group_data);
}

void TestLog(void *packer) {
  static_cast<LightmapPackerImpl *>(packer)->TestLog();
}

void SetLogCallBack(void *packer, void (*log_callback)(const char *message)) {
  static_cast<LightmapPackerImpl *>(packer)->SetLogCallBack(log_callback);
}
}
