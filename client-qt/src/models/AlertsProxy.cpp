#include "rakshak/models/AlertsProxy.h"
#include <QtCore/QAbstractItemModel>

AlertsProxy::AlertsProxy(QObject* parent) : QSortFilterProxyModel(parent) {
    setFilterCaseSensitivity(Qt::CaseInsensitive);
}

void AlertsProxy::setSeverityFilter(const QString& sev) {
    m_severity = sev;
    invalidateFilter();
}

void AlertsProxy::setTextFilter(const QString& text) {
    m_text = text;
    invalidateFilter();
}

bool AlertsProxy::filterAcceptsRow(int srcRow, const QModelIndex& parent) const {
    auto m = sourceModel();
    if (!m) return true;
    auto idxSeverity = m->index(srcRow, 1, parent);
    auto idxAll = [m,srcRow,&parent](int col){ return m->index(srcRow,col,parent); };

    if (m_severity != "All") {
        if (m->data(idxSeverity, Qt::DisplayRole).toString().compare(m_severity, Qt::CaseInsensitive) != 0)
            return false;
    }
    if (!m_text.isEmpty()) {
        bool matched = false;
        for (int c : {0,2,3,4}) {
            QString v = m->data(idxAll(c), Qt::DisplayRole).toString();
            if (v.contains(m_text, Qt::CaseInsensitive)) { matched = true; break; }
        }
        if (!matched) return false;
    }
    return true;
}