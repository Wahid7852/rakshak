#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>
#include <rakshak/backend/ApiClient.h>

class QLabel;
class QPushButton;
class QProgressBar;
class QLineEdit;

namespace rakshak::pages {

// Real file scanning: picks a file, uploads it to /v1/scan/file via
// ApiClient, and reports the actual verdict - no simulated progress, no
// QRandomGenerator confidence score.
class ScanPage : public QWidget {
    Q_OBJECT
public:
    explicit ScanPage(rakshak::backend::ApiClient* api, QWidget* parent = nullptr);

signals:
    void fileScanReady(const QString& path, const rakshak::backend::FileScanResult& result);
    void logLineScanReady(const QString& line, const rakshak::backend::LogScanResult& result);

private slots:
    void onChooseFile();
    void onScanClicked();
    void onCheckLineClicked();

private:
    rakshak::backend::ApiClient* m_api;
    QString m_selectedPath;
    QString m_context;

    QLabel* m_selectedFileLabel;
    QPushButton* m_chooseButton;
    QPushButton* m_scanButton;
    QProgressBar* m_progress;
    QLineEdit* m_logLineInput;
    QPushButton* m_checkLineButton;
};

} // namespace rakshak::pages
