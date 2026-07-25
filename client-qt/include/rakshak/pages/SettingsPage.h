#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>
#include <rakshak/backend/ApiClient.h>

class QLineEdit;
class QLabel;
class QPushButton;

namespace rakshak::pages {

// Bound 1:1 to rakshak::common::SettingsData - and only to fields that are
// actually consumed somewhere (logPath drives real log tailing, apiBaseUrl/
// apiKey drive ApiClient). No decorative fields nothing reads.
class SettingsPage : public QWidget {
    Q_OBJECT
public:
    explicit SettingsPage(rakshak::backend::ApiClient* api, QWidget* parent = nullptr);

signals:
    void statusMessage(const QString& message, bool isError);
    // Fired after Save or Restore Defaults - MainWindow re-reads Settings to
    // restart/stop log monitoring and re-apply the theme.
    void settingsApplied();

private slots:
    void onBrowseLogPath();
    void onSaveClicked();
    void onRestoreDefaultsClicked();
    void onTestConnectionClicked();

private:
    void loadFromSettings();

    rakshak::backend::ApiClient* m_api;

    QLineEdit* m_logPathInput;
    QPushButton* m_browseButton;
    QLineEdit* m_apiBaseUrlInput;
    QLineEdit* m_apiKeyInput;
    QPushButton* m_saveButton;
    QPushButton* m_restoreDefaultsButton;
    QPushButton* m_testConnectionButton;
    QLabel* m_testResultLabel;
};

} // namespace rakshak::pages
