#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>
#include <rakshak/backend/ApiClient.h>

class QLabel;
class QPushButton;

namespace rakshak::pages {

// Pure display of a real FileScanResult or LogScanResult - no data of its own.
class ScanResultPage : public QWidget {
    Q_OBJECT
public:
    explicit ScanResultPage(QWidget* parent = nullptr);

    void setFileResult(const QString& path, const rakshak::backend::FileScanResult& result);
    void setLogResult(const QString& line, const rakshak::backend::LogScanResult& result);

signals:
    void backRequested();
    void viewQuarantineRequested();

private:
    void applySeverity(bool alarmed);

    QLabel* m_subjectLabel;
    QLabel* m_verdictLabel;
    QLabel* m_scoreLabel;
    QLabel* m_modelLabel;
    QLabel* m_reasonLabel;
    QLabel* m_shaLabel;
    QLabel* m_quarantineLabel;
    QPushButton* m_viewQuarantineButton;
};

} // namespace rakshak::pages
