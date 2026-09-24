/**
 * violation_detector_node.cpp
 *
 * 功能：
 *  1. 從 zones.yaml 載入違停多邊形區域（GIMP 像素座標 → ROS 世界座標）
 *  2. 訂閱 /detected_vehicles (vision_msgs::msg::Detection3DArray)
 *  3. 當偵測車輛的 map frame centroid 落入任意區域時，觸發「違停警報」
 *  4. 在 /violation_markers (visualization_msgs::msg::MarkerArray) 發布：
 *       - 永久紅色標注框（2D 地圖平面上的 LINE_STRIP）
 *       - 紅色文字 ID 標籤
 *  5. 同時發布 /violation_zones_markers，在 RViz 中顯示所有違停區域的邊界線（供除錯）
 */

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "geometry_msgs/msg/point_stamped.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "visualization_msgs/msg/marker.hpp"
#include "visualization_msgs/msg/marker_array.hpp"
#include "vision_msgs/msg/detection3_d_array.hpp"
#include "tf2_ros/buffer.h"
#include "tf2_ros/transform_listener.h"
#if __has_include(<tf2_geometry_msgs/tf2_geometry_msgs.hpp>)
  #include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#else
  #include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#endif

#include "yaml-cpp/yaml.h"

#include "violation_detector/zone.hpp"

using namespace std::chrono_literals;
using violation_detector::Zone;
using violation_detector::point_in_polygon;

// ─────────────────────────────────────────────────────────────────────────────

class ViolationDetectorNode : public rclcpp::Node
{
public:
  ViolationDetectorNode()
  : Node("violation_detector")
  {
    // ── 參數宣告 ─────────────────────────────────────────────────────────────
    declare_parameter<std::string>("zones_yaml_path",
      "/home/ntust/fish/ros2_ws/violation_area/zones.yaml");
    declare_parameter<std::string>("vehicles_topic",   "/detected_vehicles");
    declare_parameter<std::string>("map_frame",        "map");
    declare_parameter<double>("confirm_duration_sec",  3.0);   // 停留幾秒才觸發
    declare_parameter<double>("marker_z",              0.05);  // 標注框距地面高度 (m)
    declare_parameter<double>("marker_height",         1.8);   // 標注框高度 (m)
    declare_parameter<double>("zone_line_width",       0.15);  // 區域邊框線寬 (m)
    declare_parameter<double>("zone_buffer_m",         1.0);   // 判定區域往外擴展 (m)，補足車輛壓線漏判
    declare_parameter<double>("track_dist_thresh",     1.2);   // 空間匹配距離門檻 (m)，解決配準/位移抖動
    declare_parameter<double>("max_disappear_sec",     2.0);   // 允許幾秒未偵測到才移除軌跡 (s)
    declare_parameter<double>("violation_cooldown_sec", 30.0);  // 相同區域防止重複記違停的冷卻時間 (s)

    zones_yaml_path_       = get_parameter("zones_yaml_path").as_string();
    vehicles_topic_        = get_parameter("vehicles_topic").as_string();
    map_frame_             = get_parameter("map_frame").as_string();
    confirm_duration_      = rclcpp::Duration::from_seconds(
      get_parameter("confirm_duration_sec").as_double());
    marker_z_               = get_parameter("marker_z").as_double();
    marker_height_          = get_parameter("marker_height").as_double();
    zone_line_width_        = get_parameter("zone_line_width").as_double();
    zone_buffer_m_          = get_parameter("zone_buffer_m").as_double();
    track_dist_thresh_      = get_parameter("track_dist_thresh").as_double();
    max_disappear_sec_      = get_parameter("max_disappear_sec").as_double();
    violation_cooldown_sec_ = get_parameter("violation_cooldown_sec").as_double();

    // ── 載入違停區域 ──────────────────────────────────────────────────────────
    load_zones(zones_yaml_path_);
    RCLCPP_INFO(get_logger(), "Loaded %zu violation zones from: %s",
      zones_.size(), zones_yaml_path_.c_str());

    // ── TF ───────────────────────────────────────────────────────────────────
    tf_buffer_   = std::make_shared<tf2_ros::Buffer>(get_clock());
    tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);

    // ── 發布者 ───────────────────────────────────────────────────────────────
    pub_violation_ = create_publisher<visualization_msgs::msg::MarkerArray>(
      "/violation_markers", rclcpp::QoS(10).transient_local());  // latching: 讓 RViz 重連後也能看到
    pub_zones_     = create_publisher<visualization_msgs::msg::MarkerArray>(
      "/violation_zones_markers", rclcpp::QoS(10).transient_local());

    pub_nav_target_ = create_publisher<geometry_msgs::msg::PoseStamped>(
      "/violation/nav_target", 10);
    pub_camera_trigger_ = create_publisher<std_msgs::msg::String>(
      "/violation/camera_trigger", 10);

    // ── 訂閱者 ───────────────────────────────────────────────────────────────
    sub_vehicles_ = create_subscription<vision_msgs::msg::Detection3DArray>(
      vehicles_topic_, 10,
      std::bind(&ViolationDetectorNode::cb_vehicles, this, std::placeholders::_1));

    // ── 定時發布違停區域輪廓（供 RViz 除錯顯示） ────────────────────────────
    timer_zones_ = create_wall_timer(2s,
      std::bind(&ViolationDetectorNode::publish_zone_outlines, this));

    publish_zone_outlines();  // 啟動後立即發布一次
    RCLCPP_INFO(get_logger(), "ViolationDetectorNode started. Listening to: %s",
      vehicles_topic_.c_str());
  }

private:
  // ── 從 YAML 載入違停區域 ────────────────────────────────────────────────────
  void load_zones(const std::string & path)
  {
    YAML::Node doc = YAML::LoadFile(path);

    auto info = doc["map_info"];
    double res = info["resolution"].as<double>();
    double ox  = info["origin"][0].as<double>();
    double oy  = info["origin"][1].as<double>();
    int    h   = info["image_height"].as<int>();

    for (auto it = doc["zones"].begin(); it != doc["zones"].end(); ++it) {
      Zone z;
      z.name = it->first.as<std::string>();
      for (const auto & pt : it->second) {
        int px = pt[0].as<int>();
        int py = pt[1].as<int>();
        // 核心轉換：GIMP 左上原點 → ROS 左下世界座標
        double wx = px * res + ox;
        double wy = (h - py) * res + oy;
        z.vertices.push_back({wx, wy});
      }
      zones_.push_back(z);
    }
  }

  // ── 收到車輛偵測結果 ────────────────────────────────────────────────────────
  void cb_vehicles(const vision_msgs::msg::Detection3DArray::SharedPtr msg)
  {
    auto now = this->now();

    // 追蹤哪些 vehicle ID 本幀出現過
    std::set<std::string> seen_ids;

    for (auto & det : msg->detections) {
      // detection 的 frame 通常是 base_link/os_lidar，需要轉換至 map frame
      // 使用 Time(0) = 最新可用 TF，避免 bag 硬體時間戳與 sim_time 未同步導致 lookup 失敗
      geometry_msgs::msg::PoseStamped pose_in, pose_map;
      pose_in.header.frame_id = msg->header.frame_id;
      pose_in.header.stamp    = rclcpp::Time(0);   // latest available
      pose_in.pose            = det.bbox.center;

      try {
        tf_buffer_->transform(pose_in, pose_map, map_frame_, tf2::durationFromSec(0.1));
      } catch (const tf2::TransformException & ex) {
        RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000,
          "TF transform failed: %s", ex.what());
        continue;
      }

      double cx = pose_map.pose.position.x;
      double cy = pose_map.pose.position.y;

      // 確認哪個 zone 包含此車輛（質心 + 4 個角點，任一命中即觸發）
      // 同時支援 zone_buffer_m_ 膨脹容差（補足車輛壓線漏判）
      std::string hit_zone;
      {
        // 從四元數計算 yaw
        const auto & q = pose_map.pose.orientation;
        double yaw = std::atan2(
          2.0 * (q.w * q.z + q.x * q.y),
          1.0 - 2.0 * (q.y * q.y + q.z * q.z));

        // bbox 半長/半寬 + buffer 容差
        double hl = det.bbox.size.x / 2.0 + zone_buffer_m_;
        double hw = det.bbox.size.y / 2.0 + zone_buffer_m_;
        double cos_y = std::cos(yaw), sin_y = std::sin(yaw);

        // 5 個採樣點：質心 + 4 個旋轉角點
        std::vector<std::array<double, 2>> check_pts = {
          {cx, cy},
          {cx + hl * cos_y - hw * sin_y,  cy + hl * sin_y + hw * cos_y},
          {cx + hl * cos_y + hw * sin_y,  cy + hl * sin_y - hw * cos_y},
          {cx - hl * cos_y - hw * sin_y,  cy - hl * sin_y + hw * cos_y},
          {cx - hl * cos_y + hw * sin_y,  cy - hl * sin_y - hw * cos_y},
        };

        for (auto & z : zones_) {
          for (auto & pt : check_pts) {
            if (point_in_polygon(pt[0], pt[1], z.vertices)) {
              hit_zone = z.name;
              break;
            }
          }
          if (!hit_zone.empty()) break;
        }
      }

      // ── 空間 Nearest-Neighbor 追蹤關聯 ──
      // 搜尋 2.0 公尺內已存在的跨幀車輛，解決點雲配準與相對位移微幅抖動問題
      int best_idx = -1;
      double min_dist = std::numeric_limits<double>::max();

      for (size_t i = 0; i < tracked_vehicles_.size(); ++i) {
        double dist = std::hypot(cx - tracked_vehicles_[i].cx, cy - tracked_vehicles_[i].cy);
        if (dist < track_dist_thresh_ && dist < min_dist) {
          min_dist = dist;
          best_idx = static_cast<int>(i);
        }
      }

      if (best_idx >= 0) {
        // 匹配成功：平滑更新地圖質心位置，保留原始進入時間 enter_time
        auto & track = tracked_vehicles_[best_idx];
        track.cx = 0.7 * track.cx + 0.3 * cx;
        track.cy = 0.7 * track.cy + 0.3 * cy;
        track.last_seen_time = now;

        if (!hit_zone.empty()) {
          if (track.hit_zone.empty()) {
            track.hit_zone = hit_zone;
            track.enter_time = now;
            RCLCPP_INFO(get_logger(), "Vehicle '%s' entered zone '%s'",
              track.id.c_str(), hit_zone.c_str());
          }

          // 檢測停留時長
          rclcpp::Duration dwell = now - track.enter_time;
          if (dwell >= confirm_duration_ && !track.is_confirmed) {
            track.is_confirmed = true;

            // 清理超過 30 秒的過期冷卻記錄
            for (auto it = confirmed_records_.begin(); it != confirmed_records_.end(); ) {
              if ((now - it->confirmed_time).seconds() > violation_cooldown_sec_) {
                it = confirmed_records_.erase(it);
              } else {
                ++it;
              }
            }

            // 檢查在 2.0 公尺且 30 秒內是否已經觸發過違停
            bool is_duplicate = false;
            for (const auto & rec : confirmed_records_) {
              double dist = std::hypot(track.cx - rec.cx, track.cy - rec.cy);
              if (dist < 2.0) {
                is_duplicate = true;
                break;
              }
            }

            if (!is_duplicate) {
              confirmed_records_.push_back({track.cx, track.cy, track.hit_zone, now});
              RCLCPP_WARN(get_logger(),
                "[VIOLATION] Vehicle '%s' in zone '%s' for %.1fs!",
                track.id.c_str(), track.hit_zone.c_str(), dwell.seconds());
              publish_violation_marker(track.id, track.hit_zone, track.cx, track.cy);
              publish_nav_target(track.cx, track.cy);
              publish_camera_trigger(track.id, track.hit_zone, track.cx, track.cy);
              // trigger_cloud_upload(track.hit_zone, track.cx, track.cy); // 舊版無照片上傳 (已由相機拍照上傳節點取代)
            } else {
              RCLCPP_INFO(get_logger(),
                "[SUPPRESSED] Duplicate violation suppressed for vehicle '%s' at (%.1f, %.1f) within 30s cooldown",
                track.id.c_str(), track.cx, track.cy);
            }
          }
        } else {
          track.hit_zone = "";
        }
      } else if (!hit_zone.empty()) {
        // 未匹配且進入違停區域：建立全新車輛軌跡
        // 優先使用 detector_node 傳來的 std::string("")（已在 map 座標系計算的 v_gx_gy）
        std::string base_id;
        if (!std::string("").empty()) {
          base_id = std::string("");
        } else {
          int gx = static_cast<int>(std::round(cx));
          int gy = static_cast<int>(std::round(cy));
          base_id = "v_" + std::to_string(gx) + "_" + std::to_string(gy);
        }
        std::string veh_id = base_id;

        int dup_counter = 1;
        while ([this](const std::string & id) {
          for (const auto & tv : tracked_vehicles_) { if (tv.id == id) return true; }
          return false;
        }(veh_id)) {
          veh_id = base_id + "_" + std::to_string(dup_counter++);
        }

        TrackedVehicle tv;
        tv.id = veh_id;
        tv.cx = cx;
        tv.cy = cy;
        tv.enter_time = now;
        tv.last_seen_time = now;
        tv.hit_zone = hit_zone;
        tv.is_confirmed = false;

        tracked_vehicles_.push_back(tv);
        RCLCPP_INFO(get_logger(), "Vehicle '%s' entered zone '%s'",
          veh_id.c_str(), hit_zone.c_str());
      }
    }

    // 清理逾時未偵測到的車輛（容忍最高 2 秒的短暫影格丟失/遮擋）
    for (auto it = tracked_vehicles_.begin(); it != tracked_vehicles_.end(); ) {
      double absent_sec = (now - it->last_seen_time).seconds();
      if (absent_sec > max_disappear_sec_) {
        it = tracked_vehicles_.erase(it);
      } else {
        ++it;
      }
    }
  }

  // ── 發布單一違停的永久 Marker ───────────────────────────────────────────────
  void publish_violation_marker(
    const std::string & veh_id,
    const std::string & zone_name,
    double cx, double cy)
  {
    visualization_msgs::msg::MarkerArray ma;
    int id_int = static_cast<int>(violation_marker_id_++);

    // ── 紅色立方體（2D 地圖平面上的薄方形） ──
    {
      visualization_msgs::msg::Marker box;
      box.header.frame_id = map_frame_;
      box.header.stamp    = now();
      box.ns              = "violations";
      box.id              = id_int * 2;
      box.type            = visualization_msgs::msg::Marker::CUBE;
      box.action          = visualization_msgs::msg::Marker::ADD;
      box.pose.position.x = cx;
      box.pose.position.y = cy;
      box.pose.position.z = marker_z_ + marker_height_ / 2.0;
      box.pose.orientation.w = 1.0;
      box.scale.x = 4.5;             // 車輛約 4.5m 長
      box.scale.y = 2.0;             // 車輛約 2.0m 寬
      box.scale.z = marker_height_;
      box.color.r = 1.0f;
      box.color.g = 0.0f;
      box.color.b = 0.0f;
      box.color.a = 0.35f;
      box.lifetime = rclcpp::Duration(0, 0);  // 永久
      ma.markers.push_back(box);
    }

    // ── 紅色文字標籤 ──
    {
      visualization_msgs::msg::Marker txt;
      txt.header.frame_id = map_frame_;
      txt.header.stamp    = now();
      txt.ns              = "violations_text";
      txt.id              = id_int * 2 + 1;
      txt.type            = visualization_msgs::msg::Marker::TEXT_VIEW_FACING;
      txt.action          = visualization_msgs::msg::Marker::ADD;
      txt.pose.position.x = cx;
      txt.pose.position.y = cy;
      txt.pose.position.z = marker_z_ + marker_height_ + 0.5;
      txt.pose.orientation.w = 1.0;
      txt.scale.z = 1.0;  // 文字高度 (m)
      txt.color.r = 1.0f;
      txt.color.g = 0.2f;
      txt.color.b = 0.2f;
      txt.color.a = 1.0f;
      txt.text    = "違停 [" + zone_name + "]\n" + veh_id;
      txt.lifetime = rclcpp::Duration(0, 0);
      ma.markers.push_back(txt);
    }

    pub_violation_->publish(ma);
  }

  // ── 定期發布違停區域輪廓（LINE_STRIP）供 RViz 除錯顯示 ───────────────────
  void publish_zone_outlines()
  {
    visualization_msgs::msg::MarkerArray ma;
    int id = 0;

    for (auto & z : zones_) {
      visualization_msgs::msg::Marker line;
      line.header.frame_id = map_frame_;
      line.header.stamp    = now();
      line.ns              = "violation_zones";
      line.id              = id++;
      line.type            = visualization_msgs::msg::Marker::LINE_STRIP;
      line.action          = visualization_msgs::msg::Marker::ADD;
      line.pose.orientation.w = 1.0;
      line.scale.x         = zone_line_width_;
      line.color.r         = 1.0f;
      line.color.g         = 0.6f;
      line.color.b         = 0.0f;
      line.color.a         = 0.8f;
      line.lifetime        = rclcpp::Duration(0, 0);

      for (auto & v : z.vertices) {
        geometry_msgs::msg::Point p;
        p.x = v[0];  p.y = v[1];  p.z = marker_z_;
        line.points.push_back(p);
      }
      // 閉合多邊形
      if (!z.vertices.empty()) {
        geometry_msgs::msg::Point p;
        p.x = z.vertices[0][0];  p.y = z.vertices[0][1];  p.z = marker_z_;
        line.points.push_back(p);
      }
      ma.markers.push_back(line);

      // 在多邊形中心標注區域名稱
      visualization_msgs::msg::Marker txt;
      txt.header.frame_id = map_frame_;
      txt.header.stamp    = now();
      txt.ns              = "violation_zones_text";
      txt.id              = id++;
      txt.type            = visualization_msgs::msg::Marker::TEXT_VIEW_FACING;
      txt.action          = visualization_msgs::msg::Marker::ADD;
      txt.scale.z         = 1.5;
      txt.color.r = 1.0f;  txt.color.g = 0.7f;  txt.color.b = 0.0f;
      txt.color.a = 1.0f;
      txt.text            = z.name;
      txt.lifetime        = rclcpp::Duration(0, 0);

      // 計算中心
      double sx = 0, sy = 0;
      for (auto & v : z.vertices) { sx += v[0]; sy += v[1]; }
      txt.pose.position.x = sx / z.vertices.size();
      txt.pose.position.y = sy / z.vertices.size();
      txt.pose.position.z = marker_z_ + 2.0;
      txt.pose.orientation.w = 1.0;
      ma.markers.push_back(txt);
    }

    pub_zones_->publish(ma);
  }

  // ── 發布車輛側邊觀測導航點至 /violation/nav_target ──────────────────────
  void publish_nav_target(double cx, double cy)
  {
    geometry_msgs::msg::PoseStamped target;
    target.header.frame_id = map_frame_;
    target.header.stamp    = now();
    target.pose.position.x = cx - 1.5;  // 側邊平行觀測點 (偏 1.5m)
    target.pose.position.y = cy;
    target.pose.position.z = 0.0;
    target.pose.orientation.w = 1.0;
    pub_nav_target_->publish(target);
  }

  // ── 發布相機拍攝與上傳觸發訊號至 /violation/camera_trigger ────────────────
  void publish_camera_trigger(
    const std::string & veh_id,
    const std::string & zone_name,
    double cx, double cy)
  {
    // 地圖參數 (轉像素座標: resolution=0.12, origin=[-339, -141], height=5642)
    double res = 0.12;
    double ox = -339.0;
    double oy = -141.0;
    int h = 5642;

    double px = (cx - ox) / res;
    double py = static_cast<double>(h) - ((cy - oy) / res);

    std_msgs::msg::String msg;
    msg.data = "{\"vehicle_id\":\"" + veh_id +
               "\",\"zone_name\":\"" + zone_name +
               "\",\"cx\":" + std::to_string(cx) +
               ",\"cy\":" + std::to_string(cy) +
               ",\"px\":" + std::to_string(px) +
               ",\"py\":" + std::to_string(py) + "}";

    pub_camera_trigger_->publish(msg);
  }

  // ── 觸發雲端 Google Sheets 自動上傳 ──────────────────────────────────────
  void trigger_cloud_upload(const std::string & zone_name, double cx, double cy)
  {
    std::thread([this, zone_name, cx, cy]() {
      std::string uploader_path = "/home/ntust/fish/ros2_ws/violation_uploader.py";
      std::string cmd = "python3 " + uploader_path +
                        " --zone \"" + zone_name + "\"" +
                        " --cx " + std::to_string(cx) +
                        " --cy " + std::to_string(cy) + " > /dev/null 2>&1";
      int res = std::system(cmd.c_str());
      (void)res;
    }).detach();
  }

  // ── 成員變數 ────────────────────────────────────────────────────────────────
  std::string zones_yaml_path_;
  std::string vehicles_topic_;
  std::string map_frame_;
  rclcpp::Duration confirm_duration_{3, 0};
  double marker_z_;
  double marker_height_;
  double zone_line_width_;
  double zone_buffer_m_;
  double track_dist_thresh_;
  double max_disappear_sec_;
  double violation_cooldown_sec_;

  std::vector<Zone> zones_;

  struct TrackedVehicle {
    std::string id;
    double cx;
    double cy;
    rclcpp::Time enter_time;
    rclcpp::Time last_seen_time;
    std::string hit_zone;
    bool is_confirmed = false;
  };

  struct ConfirmedViolationRecord {
    double cx;
    double cy;
    std::string zone_name;
    rclcpp::Time confirmed_time;
  };

  std::vector<TrackedVehicle> tracked_vehicles_;
  std::vector<ConfirmedViolationRecord> confirmed_records_;

  int violation_marker_id_ = 0;

  std::shared_ptr<tf2_ros::Buffer>            tf_buffer_;
  std::shared_ptr<tf2_ros::TransformListener> tf_listener_;

  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_violation_;
  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_zones_;
  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr      pub_nav_target_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr               pub_camera_trigger_;
  rclcpp::Subscription<vision_msgs::msg::Detection3DArray>::SharedPtr sub_vehicles_;
  rclcpp::TimerBase::SharedPtr timer_zones_;
};

// ─────────────────────────────────────────────────────────────────────────────

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ViolationDetectorNode>());
  rclcpp::shutdown();
  return 0;
}
