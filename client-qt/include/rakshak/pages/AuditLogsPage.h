#pragma once
#include <QtWidgets/QWidget>

class QTableView;
class AuditModel;

namespace rakshak::pages {

// Displays real lifecycle events (monitor start/stop, scans, quarantine
// actions, settings changes, backend reachability) pushed into AuditModel
// from MainWindow. Unlike the PR's version, this constructor does something.
class AuditLogsPage : public QWidget {
    Q_OBJECT
public:
    explicit AuditLogsPage(AuditModel* auditModel, QWidget* parent = nullptr);

private:
    AuditModel* m_auditModel;
    QTableView* m_table;
};

} // namespace rakshak::pages
