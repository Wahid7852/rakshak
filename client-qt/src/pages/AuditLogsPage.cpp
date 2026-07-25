#include <rakshak/pages/AuditLogsPage.h>
#include <rakshak/models/AuditModel.h>
#include <rakshak/common/UiState.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QTableView>
#include <QtWidgets/QHeaderView>
#include <QtCore/QAbstractItemModel>

using namespace rakshak::pages;

AuditLogsPage::AuditLogsPage(AuditModel* auditModel, QWidget* parent)
    : QWidget(parent), m_auditModel(auditModel) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(8);

    auto* title = new QLabel(tr("Audit log"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    auto* subtitle = new QLabel(tr("Every monitoring start/stop, scan, quarantine action, and settings change, in order."), this);
    subtitle->setObjectName("statusSentence");
    subtitle->setWordWrap(true);
    layout->addWidget(subtitle);

    m_table = new QTableView(this);
    m_table->setModel(m_auditModel);
    m_table->setShowGrid(false);
    m_table->verticalHeader()->hide();
    m_table->setWordWrap(true);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    layout->addWidget(m_table, 1);

    m_table->resizeColumnsToContents();
    m_table->horizontalHeader()->restoreState(rakshak::common::loadUiState("auditlogs.table"));
    connect(m_table->horizontalHeader(), &QHeaderView::sectionResized, this, [this] {
        rakshak::common::saveUiState("auditlogs.table", m_table->horizontalHeader()->saveState());
    });
    connect(m_auditModel, &QAbstractItemModel::rowsInserted, m_table, &QTableView::resizeRowsToContents);
}
