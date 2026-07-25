#include "rakshak/models/AlertsModel.h"
#include <QtCore/QModelIndex>
#include <QtGui/QBrush>

AlertsModel::AlertsModel(QObject* parent) : QAbstractTableModel(parent) {}

int AlertsModel::rowCount(const QModelIndex&) const { return m_rows.size(); }
int AlertsModel::columnCount(const QModelIndex&) const { return 6; }

QVariant AlertsModel::data(const QModelIndex& idx, int role) const {
    if (!idx.isValid() || idx.row() < 0 || idx.row() >= m_rows.size()) return {};
    const auto& r = m_rows[idx.row()];
    if (role == Qt::DisplayRole) {
        switch (idx.column()) {
        case 0: return r.timestamp;
        case 1: return r.severity;
        case 2: return r.srcIp;
        case 3: return r.dstIp;
        case 4: return r.ruleId;
        case 5: return r.score;
        }
    }
    if (role == Qt::ForegroundRole) {
        if (r.severity == "High" || r.severity == "Critical") {
            return QBrush(Qt::red);
        }
    }
    return {};
}

QVariant AlertsModel::headerData(int section, Qt::Orientation o, int role) const {
    if (o == Qt::Horizontal && role == Qt::DisplayRole) {
        switch (section) {
        case 0: return "Time";
        case 1: return "Severity";
        case 2: return "Src IP";
        case 3: return "Dst IP";
        case 4: return "Rule";
        case 5: return "Score";
        }
    }
    return {};
}

void AlertsModel::addAlert(const AlertRow& row) {
    int newRow = m_rows.size();
    beginInsertRows(QModelIndex(), newRow, newRow);
    m_rows.push_back(row);
    endInsertRows();
    if (m_rows.size() > m_maxRows) {
        beginRemoveRows(QModelIndex(), 0, 0);
        m_rows.pop_front();
        endRemoveRows();
    }
}