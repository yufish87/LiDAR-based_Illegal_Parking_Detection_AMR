#pragma once
#include <string>
#include <vector>
#include <array>

namespace violation_detector
{

/** 違停區域：由 zones.yaml 載入後，頂點已換算為 ROS 世界座標 (m) */
struct Zone
{
  std::string name;
  /// polygon 頂點，順序與 yaml 一致，座標為 ROS map frame (m)
  std::vector<std::array<double, 2>> vertices;  // {wx, wy}
};

/** 判斷點 (px, py) 是否落在多邊形內（Ray-casting algorithm） */
inline bool point_in_polygon(
  double px, double py,
  const std::vector<std::array<double, 2>> & poly)
{
  bool inside = false;
  size_t n = poly.size();
  for (size_t i = 0, j = n - 1; i < n; j = i++) {
    double xi = poly[i][0], yi = poly[i][1];
    double xj = poly[j][0], yj = poly[j][1];
    bool cond = ((yi > py) != (yj > py)) &&
                (px < (xj - xi) * (py - yi) / (yj - yi) + xi);
    if (cond) inside = !inside;
  }
  return inside;
}

}  // namespace violation_detector
