#include "rakshak/models/AuditModel.h"
#include <QtCore/QDateTime>
#include <QtCore/QModelIndex>

AuditModel::AuditModel(QObject* parent) : QAbstractTableModel(parent) {}

int AuditModel::rowCount(const QModelIndex& parent) const
{
    Q_UNUSED(parent);
    return static_cast<int>(m_rows.size());
}

int AuditModel::columnCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);
    return 6;
}

QVariant AuditModel::data(const QModelIndex& idx, int role) const {
    if (!idx.isValid() || idx.row() < 0 || idx.row() >= m_rows.size()) return {};
    const auto& r = m_rows[idx.row()];
    if (role == Qt::DisplayRole) {
        switch (idx.column()) {
        case 0: return r.timestamp;
        case 1: return r.actor;
        case 2: return r.action;
        case 3: return r.resource;
        case 4: return r.status;
        case 5: return r.hash;
        }
    }
    return {};
}

QVariant AuditModel::headerData(int section, Qt::Orientation orientation, int role) const {
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole) {
        switch (section) {
        case 0: return "Time";
        case 1: return "Actor";
        case 2: return "Action";
        case 3: return "Resource";
        case 4: return "Status";
        case 5: return "Hash";
        }
    }
    return {};
}

void AuditModel::addEvent(const QString& source, const QVariantMap& event) {
    AuditRow r;
    // Fill basic fields from event map where present
    r.timestamp = event.value("timestamp").toString();
    if (r.timestamp.isEmpty()) r.timestamp = QDateTime::currentDateTime().toString();
    r.actor = event.value("actor").toString();
    r.action = event.value("action").toString();
    r.resource = source;
    r.status = event.value("status").toString();
    r.hash = event.value("hash").toString();

    int newRow = m_rows.size();
    beginInsertRows(QModelIndex(), newRow, newRow);
    m_rows.push_back(r);
    endInsertRows();
}