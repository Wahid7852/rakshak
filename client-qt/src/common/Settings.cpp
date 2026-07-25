#include <rakshak/common/Settings.h>
#include <QtCore/QSettings>

using namespace rakshak::common;

Settings& Settings::instance() {
    static Settings s; return s;
}

Settings::Settings() {
    m_qs = new QSettings(QStringLiteral("RakshakOrg"), QStringLiteral("QuantumMLHunter"));
}

SettingsData Settings::load() const {
    SettingsData d;
    d.logPath       = m_qs->value("logs/path", d.logPath).toString();
    d.apiBaseUrl    = m_qs->value("backend/apiBaseUrl", d.apiBaseUrl).toString();
    d.apiKey        = m_qs->value("backend/apiKey", d.apiKey).toString();
    d.darkMode      = m_qs->value("ui/darkMode", d.darkMode).toBool();
    return d;
}

void Settings::save(const SettingsData& d) {
    m_qs->setValue("logs/path", d.logPath);
    m_qs->setValue("backend/apiBaseUrl", d.apiBaseUrl);
    m_qs->setValue("backend/apiKey", d.apiKey);
    m_qs->setValue("ui/darkMode", d.darkMode);
    m_qs->sync();
}
