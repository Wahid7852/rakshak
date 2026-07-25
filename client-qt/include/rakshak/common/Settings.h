#pragma once

#include <QtCore/QString>

class QSettings;

namespace rakshak::common {

struct SettingsData {
    QString logPath;
    QString apiBaseUrl = "http://127.0.0.1:8080"; // REST backend base URL
    QString apiKey = "dev-key";                    // x-api-key sent on every request
    bool darkMode = false;
};

class Settings {
public:
    static Settings& instance();
    SettingsData load() const;
    void save(const SettingsData& d);

private:
    Settings(); // sets org/app names
    QSettings* m_qs = nullptr;
};

} // namespace rakshak::common
