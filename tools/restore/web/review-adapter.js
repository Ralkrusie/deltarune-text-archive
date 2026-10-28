'use strict';
window.mountReviewPreview=function(row){
 const card=document.createElement('section');card.className='card';
 const title=document.createElement('h2');title.textContent='还原预览 · 本地框架';
 const link=document.createElement('a');link.href='index.html#'+encodeURIComponent(row.id);link.textContent='在独立试验台查看这条记录 →';
 const preview=document.createElement('div');card.append(title,link,preview);document.getElementById('detail').prepend(card);
 RestorePreview.mount(preview,RestoreModel.scene(row,window.REVIEW_DATA.assets));
};
