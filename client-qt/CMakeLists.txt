cmake_minimum_required(VERSION 3.22)
project(rakshak_gui VERSION 0.1.0 LANGUAGES CXX)

# Core setup
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Qt setup
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find Qt packages
find_package(Qt6 REQUIRED COMPONENTS Widgets Network Svg)
find_package(Threads REQUIRED)

# Define source files
set(SOURCES
    src/main.cpp
    src/MainWindow.cpp
    src/backend/BackendClient.cpp
    src/backend/ApiClient.cpp
    src/common/Settings.cpp
    src/common/UiState.cpp
    src/LogMonitor.cpp
    src/models/AlertsModel.cpp
    src/models/AlertsProxy.cpp
    src/models/AuditModel.cpp
    src/models/ArtifactsModel.cpp
    src/models/PoliciesModel.cpp
    src/models/ModelsInventoryModel.cpp
    src/QuarantineModel.cpp
    src/widgets/ToastNotification.cpp
    src/pages/DashboardPage.cpp
    src/pages/ScanPage.cpp
    src/pages/ScanResultPage.cpp
    src/pages/LogAnalysisPage.cpp
    src/pages/QuarantinePage.cpp
    src/pages/AuditLogsPage.cpp
    src/pages/SettingsPage.cpp
    src/aggregator.cpp
    src/ngram.cpp
    src/zscore.cpp
    resources/resources.qrc
)

set(HEADERS
  include/rakshak/MainWindow.h
  include/rakshak/backend/BackendClient.h
  include/rakshak/backend/ApiClient.h
  include/rakshak/common/Settings.h
  include/rakshak/common/UiState.h
  include/rakshak/LogMonitor.h
  include/rakshak/models/AlertsModel.h
  include/rakshak/models/AlertsProxy.h
  include/rakshak/models/AuditModel.h
  include/rakshak/models/ArtifactsModel.h
  include/rakshak/models/PoliciesModel.h
  include/rakshak/models/ModelsInventoryModel.h
  include/rakshak/aggregator.hpp
  include/rakshak/ngram.hpp
  include/rakshak/zscore.hpp
  include/rakshak/models/QuarantineModel.h
  include/rakshak/widgets/ToastNotification.h
  include/rakshak/pages/DashboardPage.h
  include/rakshak/pages/ScanPage.h
  include/rakshak/pages/ScanResultPage.h
  include/rakshak/pages/LogAnalysisPage.h
  include/rakshak/pages/QuarantinePage.h
  include/rakshak/pages/AuditLogsPage.h
  include/rakshak/pages/SettingsPage.h
)

# Create executable
add_executable(rakshak_gui ${SOURCES} ${HEADERS})

# Include directories
target_include_directories(rakshak_gui
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Link libraries
target_link_libraries(rakshak_gui
    PRIVATE
        Qt6::Widgets
        Qt6::Network
        Qt6::Svg
        Threads::Threads
)

# Install rules
install(TARGETS rakshak_gui
    RUNTIME DESTINATION bin
)
