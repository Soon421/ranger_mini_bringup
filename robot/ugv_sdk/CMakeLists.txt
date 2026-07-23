cmake_minimum_required(VERSION 3.5.1)
project(ugv_sdk VERSION 0.8.0)

find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    message(STATUS "Found ccache")
    set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE "${CCACHE_PROGRAM}")
endif()

## Project Options
option(BUILD_TESTING "Build tests" OFF)
option(STATIC_CHECK "Run static check" OFF)

## Detect ROS2 (ament) build
find_package(ament_cmake QUIET)
if(ament_cmake_FOUND)
    message(STATUS "Build package with ament_cmake (ROS2)")
    set(BUILD_WITH_AMENT ON)
    set(BUILD_WITHOUT_ROS OFF)
else()
    message(STATUS "Build package as standalone CMake project")
    set(BUILD_WITH_AMENT OFF)
    set(BUILD_WITHOUT_ROS ON)
endif()

## Generate symbols for IDE indexer
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(STATIC_CHECK)
    find_program(CPPCHECK cppcheck)
    if(CPPCHECK)
        message(STATUS "Found cppcheck")
        set(CMAKE_CXX_CPPCHECK cppcheck;--std=c++11;--enable=all)
    endif()
endif()

## Additional cmake module path
set(USER_CMAKE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
list(APPEND CMAKE_MODULE_PATH "${USER_CMAKE_PATH}/modules")
list(APPEND CMAKE_PREFIX_PATH "/usr/lib/${CMAKE_SYSTEM_PROCESSOR}-linux-gnu/cmake")

## C++ standard
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

## Default build type
set(default_build_type "Release")
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  message(STATUS "Setting build type to '${default_build_type}' as none was specified.")
  set(CMAKE_BUILD_TYPE "${default_build_type}" CACHE
      STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS
    "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

if(BUILD_WITHOUT_ROS)
    if(PROJECT_NAME STREQUAL CMAKE_PROJECT_NAME AND BUILD_TESTING)
        enable_testing()
        include(GoogleTest)
        set(BUILD_TESTS ON)
        message(STATUS "Tests will be built")
    else()
        set(BUILD_TESTS OFF)
    endif()

    include(GNUInstallDirs)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/${CMAKE_INSTALL_LIBDIR})
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/${CMAKE_INSTALL_LIBDIR})
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/${CMAKE_INSTALL_BINDIR})
endif()

## Build libraries
find_package(Threads REQUIRED)

add_library(${PROJECT_NAME}
    src/async_port/async_serial.cpp
    src/async_port/async_can.cpp
    src/utilities/protocol_detector.cpp
    src/mobile_robot/scout_robot.cpp
    src/mobile_robot/hunter_robot.cpp
    src/mobile_robot/bunker_robot.cpp
    src/mobile_robot/ranger_robot.cpp
    src/mobile_robot/titan_robot.cpp
    src/mobile_robot/tracer_robot.cpp
    src/protocol_v2/agilex_msg_parser_v2.c
    src/protocol_v2/protocol_v2_parser.cpp
    src/protocol_v1/agilex_msg_parser_v1.c
)
target_link_libraries(${PROJECT_NAME} PUBLIC Threads::Threads)
target_compile_definitions(${PROJECT_NAME} PUBLIC ASIO_ENABLE_OLD_SERVICES)
target_include_directories(${PROJECT_NAME} PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
    PRIVATE src)

# Build demo (standalone only)
if(BUILD_WITHOUT_ROS)
    add_subdirectory(sample)
endif()

# Build tests
if(BUILD_TESTS)
    add_subdirectory(test)
endif()

#######################################
## Installation
#######################################
if(BUILD_WITH_AMENT)
    install(TARGETS ${PROJECT_NAME}
        EXPORT export_${PROJECT_NAME}
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        RUNTIME DESTINATION bin
        INCLUDES DESTINATION include)

    install(DIRECTORY include/
        DESTINATION include)

    ament_export_include_directories(include)
    ament_export_libraries(${PROJECT_NAME})
    ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
    ament_export_dependencies(Threads)

    ament_package()

elseif(BUILD_WITHOUT_ROS)
    message(STATUS "Project will be installed to ${CMAKE_INSTALL_PREFIX} with 'make install'")

    set(INSTALL_LIBDIR ${CMAKE_INSTALL_LIBDIR} CACHE PATH "Installation directory for libraries")
    set(INSTALL_BINDIR ${CMAKE_INSTALL_BINDIR} CACHE PATH "Installation directory for executables")
    set(INSTALL_INCLUDEDIR ${CMAKE_INSTALL_INCLUDEDIR} CACHE PATH "Installation directory for header files")
    if(WIN32 AND NOT CYGWIN)
        set(DEF_INSTALL_CMAKEDIR CMake)
    else()
        set(DEF_INSTALL_CMAKEDIR share/cmake/${PROJECT_NAME})
    endif()
    set(INSTALL_CMAKEDIR ${DEF_INSTALL_CMAKEDIR} CACHE PATH "Installation directory for CMake files")

    foreach(p LIB BIN INCLUDE CMAKE)
        file(TO_NATIVE_PATH ${CMAKE_INSTALL_PREFIX}/${INSTALL_${p}DIR} _path)
        message(STATUS " - To install ${p} components to ${_path}")
        unset(_path)
    endforeach()

    install(TARGETS ${PROJECT_NAME}
        EXPORT ugv_sdkTargets
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        RUNTIME DESTINATION bin
        INCLUDES DESTINATION include)

    install(DIRECTORY include/ugv_sdk
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

    include(CMakePackageConfigHelpers)
    write_basic_package_version_file(
        ugv_sdkConfigVersion.cmake
        VERSION "${VERSION_MAJOR}.${VERSION_MINOR}.${VERSION_PATCH}"
        COMPATIBILITY SameMajorVersion)

    install(EXPORT ugv_sdkTargets
        FILE ugv_sdkTargets.cmake
        DESTINATION lib/cmake/ugv_sdk)

    configure_file(cmake/ugv_sdkConfig.cmake.in ugv_sdkConfig.cmake @ONLY)
    install(FILES "${CMAKE_CURRENT_BINARY_DIR}/ugv_sdkConfig.cmake"
                "${CMAKE_CURRENT_BINARY_DIR}/ugv_sdkConfigVersion.cmake"
            DESTINATION lib/cmake/ugv_sdk)

    set(CPACK_PACKAGE_VENDOR "Weston Robot")
    set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "UGV SDK for Robots from AgileX/WestonRobot")
    set(CPACK_PACKAGE_VERSION_MAJOR ${PROJECT_VERSION_MAJOR})
    set(CPACK_PACKAGE_VERSION_MINOR ${PROJECT_VERSION_MINOR})
    set(CPACK_PACKAGE_VERSION_PATCH ${PROJECT_VERSION_PATCH})
    set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE")
    set(CPACK_RESOURCE_FILE_README "${CMAKE_CURRENT_SOURCE_DIR}/README.md")

    set(CPACK_GENERATOR "DEB")
    set(CPACK_DEBIAN_FILE_NAME DEB-DEFAULT)
    set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Ruixiang Du (ruixiang.du@westonrobot.com)")
    set(CPACK_DEBIAN_PACKAGE_DEPENDS "libasio-dev")
    set(CPACK_SOURCE_IGNORE_FILES .git dist .*build.* /\\\\.DS_Store)
    include(CPack)
endif()
