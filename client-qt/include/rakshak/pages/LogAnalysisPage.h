#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>

class QPlainTextEdit;
class QTableView;
class QLineEdit;
class QPushButton;
class QLabel;
class AlertsModel;
class AlertsProxy;
class BackendClient;

namespace rakshak::pages {

// Real log tailing: a raw scroll of tailed lines plus a table of only the
// lines that actually came back suspicious from /v1/scan/logline - no
// hardcoded design-time rows.
class LogAnalysisPage : public QWidget {
    Q_OBJECT
public:
    explicit LogAnalysisPage(BackendClient* backend, AlertsModel* alertsModel,
                              AlertsProxy* alertsProxy, QWidget* parent = nullptr);

private slots:
    void onCheckLineClicked();

private:
    BackendClient* m_backend;
    AlertsModel* m_alertsModel;
    AlertsProxy* m_alertsProxy;
    QString m_context;

    QPlainTextEdit* m_tailView;
    QTableView* m_alertsTable;
    QLineEdit* m_checkLineInput;
    QPushButton* m_checkLineButton;
    QLabel* m_checkResultLabel;
};

} // namespace rakshak::pages
