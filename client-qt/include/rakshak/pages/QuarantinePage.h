#pragma once
#include <QtWidgets/QWidget>
#include <QtCore/QString>
#include <rakshak/backend/ApiClient.h>

class QTableView;
class QPushButton;
class QLabel;
class QuarantineModel;

namespace rakshak::pages {

// Real quarantine management: list/restore/delete against
// ApiClient::listQuarantine/restoreQuarantine/deleteQuarantine. No mock rows,
// no stub "hook backend" message boxes.
class QuarantinePage : public QWidget {
    Q_OBJECT
public:
    explicit QuarantinePage(rakshak::backend::ApiClient* api, QuarantineModel* model, QWidget* parent = nullptr);

    void refresh();

signals:
    void statusMessage(const QString& message, bool isError);

private slots:
    void onRestoreClicked();
    void onDeleteClicked();

private:
    QString selectedQuarantineId() const;

    rakshak::backend::ApiClient* m_api;
    QuarantineModel* m_model;
    QTableView* m_table;
    QPushButton* m_refreshButton;
    QPushButton* m_restoreButton;
    QPushButton* m_deleteButton;
    QLabel* m_emptyLabel;
};

} // namespace rakshak::pages
