#include <rakshak/pages/QuarantinePage.h>
#include <rakshak/models/QuarantineModel.h>
#include <rakshak/common/UiState.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QTableView>
#include <QtWidgets/QHeaderView>
#include <QtCore/QItemSelectionModel>
#include <QtCore/QAbstractItemModel>
#include <QtCore/QDateTime>

using namespace rakshak::pages;
using rakshak::backend::ApiClient;
using rakshak::backend::QuarantineEntryDto;

QuarantinePage::QuarantinePage(ApiClient* api, QuarantineModel* model, QWidget* parent)
    : QWidget(parent), m_api(api), m_model(model) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(8);

    auto* title = new QLabel(tr("Quarantine"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    m_emptyLabel = new QLabel(tr("Real quarantine store, listed from /v1/quarantine."), this);
    m_emptyLabel->setObjectName("statusSentence");
    m_emptyLabel->setWordWrap(true);
    layout->addWidget(m_emptyLabel);

    auto* buttonRow = new QHBoxLayout();
    m_refreshButton = new QPushButton(tr("Refresh"), this);
    m_restoreButton = new QPushButton(tr("Restore"), this);
    m_restoreButton->setEnabled(false);
    m_deleteButton = new QPushButton(tr("Delete permanently"), this);
    m_deleteButton->setProperty("role", "danger");
    m_deleteButton->setEnabled(false);
    buttonRow->addWidget(m_refreshButton);
    buttonRow->addStretch();
    buttonRow->addWidget(m_restoreButton);
    buttonRow->addWidget(m_deleteButton);
    layout->addLayout(buttonRow);

    m_table = new QTableView(this);
    m_table->setModel(m_model);
    m_table->setShowGrid(false);
    m_table->verticalHeader()->hide();
    m_table->setWordWrap(true);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    layout->addWidget(m_table, 1);

    m_table->resizeColumnsToContents();
    m_table->horizontalHeader()->restoreState(rakshak::common::loadUiState("quarantine.table"));
    connect(m_table->horizontalHeader(), &QHeaderView::sectionResized, this, [this] {
        rakshak::common::saveUiState("quarantine.table", m_table->horizontalHeader()->saveState());
    });
    connect(m_model, &QAbstractItemModel::modelReset, m_table, &QTableView::resizeRowsToContents);

    connect(m_refreshButton, &QPushButton::clicked, this, &QuarantinePage::refresh);
    connect(m_restoreButton, &QPushButton::clicked, this, &QuarantinePage::onRestoreClicked);
    connect(m_deleteButton, &QPushButton::clicked, this, &QuarantinePage::onDeleteClicked);
    connect(m_table->selectionModel(), &QItemSelectionModel::selectionChanged, this, [this] {
        const bool hasSelection = !selectedQuarantineId().isEmpty();
        m_restoreButton->setEnabled(hasSelection);
        m_deleteButton->setEnabled(hasSelection);
    });

    connect(m_api, &ApiClient::quarantineListResult, this, [this](const QVector<QuarantineEntryDto>& entries) {
        QVector<QuarantineRow> rows;
        rows.reserve(entries.size());
        for (const auto& e : entries) {
            QuarantineRow r;
            r.quarantineId = e.quarantineId;
            r.time = QDateTime::fromSecsSinceEpoch(static_cast<qint64>(e.timestamp)).toString(Qt::ISODate);
            r.filePath = e.originalPath;
            r.reason = e.reason;
            r.sha256 = e.sha256;
            rows.push_back(r);
        }
        m_model->setRows(rows);
    });
    connect(m_api, &ApiClient::quarantineListError, this, [this](const QString& message) {
        emit statusMessage(tr("Couldn't load quarantine: %1").arg(message), true);
    });
    connect(m_api, &ApiClient::quarantineRestored, this, [this](const QString& id, bool ok, const QString& message) {
        if (ok) {
            m_model->removeRowById(id);
            emit statusMessage(tr("Restored file."), false);
        } else {
            emit statusMessage(tr("Restore failed: %1").arg(message), true);
        }
    });
    connect(m_api, &ApiClient::quarantineDeleted, this, [this](const QString& id, bool ok, const QString& message) {
        if (ok) {
            m_model->removeRowById(id);
            emit statusMessage(tr("Deleted quarantined file."), false);
        } else {
            emit statusMessage(tr("Delete failed: %1").arg(message), true);
        }
    });
}

void QuarantinePage::refresh() {
    m_api->listQuarantine();
}

QString QuarantinePage::selectedQuarantineId() const {
    const auto rows = m_table->selectionModel()->selectedRows();
    if (rows.isEmpty()) return {};
    return m_model->quarantineIdAt(rows.first().row());
}

void QuarantinePage::onRestoreClicked() {
    const auto id = selectedQuarantineId();
    if (id.isEmpty()) return;
    m_api->restoreQuarantine(id);
}

void QuarantinePage::onDeleteClicked() {
    const auto id = selectedQuarantineId();
    if (id.isEmpty()) return;
    m_api->deleteQuarantine(id);
}
